// This module intentionally has no Workers runtime import so its storage
// contract can also be exercised against SQLite outside Cloudflare.
export const CASE_TTL_SECONDS = 86400;
export const MAX_CASES_PER_OWNER = 20;
export const MAX_COMMAND_BYTES = 1024 * 1024;
const MAX_JSON_DEPTH = 32;
const MAX_JSON_NODES = 50000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const OWNER_HASH = /^[a-f0-9]{64}$/;
const encoder = new TextEncoder();
const forbiddenFields = new Set([
  'rawfile', 'rawfiles', 'filebytes', 'filecontent', 'rawcontent', 'rawtext',
  'blob', 'base64', 'dataurl', 'contentbytes', 'filedata', 'filebase64',
  'imagebase64', 'documentbytes', 'pdfbytes', 'rawdocument', 'rawdocuments',
  'key', 'apikey', 'llmapikey', 'openrouterkey', 'xopenrouterkey',
  'casestoretoken', 'authorization', 'proxyauthorization', 'credentials',
  'credential', 'secret', 'clientsecret', 'password', 'passwd', 'token',
  'accesstoken', 'refreshtoken', 'idtoken', 'privatekey', 'cookie', 'setcookie',
]);

export class CaseStoreError extends Error {
  constructor(code, message, status) {
    super(message);
    this.name = 'CaseStoreError';
    this.code = code;
    this.status = status;
  }
}

function invalid() {
  throw new CaseStoreError('VALIDATION_ERROR', '案件僅能保存有效的結構化資料與檔案中繼資料。', 422);
}

function plainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}

function normalizedField(field) {
  return field.replace(/[_\-\s]/g, '').toLowerCase();
}

function forbiddenField(field, value) {
  const normalized = normalizedField(field);
  // This is a claim-condition enum, including copies in dialogue proposals;
  // it never carries an HTTP authorization value or any credential.
  if (normalized === 'insurerrequestedmedicalauthorization') {
    return !['yes', 'no', 'unknown'].includes(value);
  }
  return forbiddenFields.has(normalized) || /(?:apikey|token|secret|password|privatekey|authorization)$/.test(normalized);
}

function validateFile(value) {
  if (value === null) return;
  if (!plainObject(value) || Object.keys(value).some(key => !['name', 'type', 'size', 'sha256'].includes(key))) invalid();
  if (typeof value.name !== 'string' || value.name.length > 255 || typeof value.type !== 'string'
    || !Number.isSafeInteger(value.size) || value.size < 1 || value.size > 10 * 1024 * 1024
    || (value.sha256 != null && (typeof value.sha256 !== 'string' || !OWNER_HASH.test(value.sha256)))) invalid();
}

function structuredCopy(value) {
  let nodes = 0;
  const ancestors = new Set();
  function visit(node, depth) {
    if (++nodes > MAX_JSON_NODES || depth > MAX_JSON_DEPTH) invalid();
    if (node === null || typeof node === 'string' || typeof node === 'boolean') return;
    if (typeof node === 'number') {
      if (!Number.isFinite(node)) invalid();
      return;
    }
    if (typeof node !== 'object' || (!Array.isArray(node) && !plainObject(node)) || ancestors.has(node)) invalid();
    ancestors.add(node);
    if (Object.getOwnPropertySymbols(node).length) invalid();
    const descriptors = Object.getOwnPropertyDescriptors(node);
    for (const [key, descriptor] of Object.entries(descriptors)) {
      if (Array.isArray(node) && key === 'length') continue;
      if (!descriptor.enumerable || !Object.hasOwn(descriptor, 'value')
        || ['__proto__', 'prototype', 'constructor'].includes(key)
        || forbiddenField(key, descriptor.value)) invalid();
      if (normalizedField(key) === 'file') validateFile(descriptor.value);
      visit(descriptor.value, depth + 1);
    }
    // JSON converts sparse array holes into null; reject that silent change.
    if (Array.isArray(node) && Object.keys(node).length !== node.length) invalid();
    ancestors.delete(node);
  }
  visit(value, 0);
  const encoded = JSON.stringify(value);
  if (encoder.encode(encoded).byteLength > MAX_COMMAND_BYTES) {
    throw new CaseStoreError('PAYLOAD_TOO_LARGE', '案件資料超過暫存大小上限。', 413);
  }
  return JSON.parse(encoded);
}

function caseId(value) {
  if (typeof value !== 'string' || !UUID.test(value)) invalid();
  return value;
}

function createdTimestamp(value) {
  if (typeof value !== 'string') invalid();
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match) invalid();
  const [, yearText, monthText, dayText, hourText, minuteText, secondText, fraction = '', zone] = match;
  const [year, month, day, hour, minute, second] = [yearText, monthText, dayText, hourText, minuteText, secondText].map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1]
    || hour > 23 || minute > 59 || second > 59
    || (zone !== 'Z' && (Number(zone.slice(1, 3)) > 23 || Number(zone.slice(4, 6)) > 59))) invalid();
  const seconds = Date.parse(`${yearText}-${monthText}-${dayText}T${hourText}:${minuteText}:${secondText}${zone}`) / 1000
    + (fraction ? Number(`0.${fraction}`) : 0);
  if (!Number.isFinite(seconds)) invalid();
  return seconds;
}

function commandInput(input, nowSeconds) {
  if (!plainObject(input) || !Number.isFinite(nowSeconds)) invalid();
  const command = structuredCopy(input);
  const fields = {
    cleanup: ['op'],
    create: ['op', 'owner_hash', 'case'],
    get: ['op', 'owner_hash', 'id'],
    save: ['op', 'owner_hash', 'case', 'expected_revision'],
    delete: ['op', 'owner_hash', 'id'],
  };
  if (typeof command.op !== 'string' || !Object.hasOwn(fields, command.op)
    || Object.keys(command).some(key => !fields[command.op].includes(key))) invalid();
  if (command.op === 'cleanup') return command;
  if (typeof command.owner_hash !== 'string' || !OWNER_HASH.test(command.owner_hash)) invalid();
  if (command.op === 'get' || command.op === 'delete') {
    caseId(command.id);
    return command;
  }
  if (!plainObject(command.case)) invalid();
  const item = command.case;
  if (command.op === 'create') {
    if (!Object.hasOwn(item, 'id')) item.id = globalThis.crypto.randomUUID();
    if (!Object.hasOwn(item, 'created_at')) item.created_at = new Date(nowSeconds * 1000).toISOString();
    if (!Object.hasOwn(item, 'updated_at')) item.updated_at = item.created_at;
    if (Object.hasOwn(item, 'revision') && item.revision !== 0) invalid();
  }
  caseId(item.id);
  if (command.op === 'create') createdTimestamp(item.created_at);
  if (Object.hasOwn(item, 'revision') && (!Number.isSafeInteger(item.revision) || item.revision < 0)) invalid();
  if (Object.hasOwn(command, 'expected_revision') && (!Number.isSafeInteger(command.expected_revision) || command.expected_revision < 0)) invalid();
  if (command.op === 'save' && Object.hasOwn(item, 'revision') && !Object.hasOwn(command, 'expected_revision')) invalid();
  return command;
}

function initialize(sql) {
  sql.exec('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, owner_hash TEXT NOT NULL, created_at REAL NOT NULL, payload TEXT NOT NULL)');
  sql.exec('CREATE INDEX IF NOT EXISTS cases_owner ON cases(owner_hash)');
  sql.exec('CREATE INDEX IF NOT EXISTS cases_created ON cases(created_at)');
}

/**
 * Execute one authenticated internal command against DurableObjectStorage.
 * The caller authenticates the request before passing parsed JSON here.
 * Returns the CaseStore value; throws only sanitized CaseStoreError values.
 */
export function executeCaseCommand(storage, input, nowSeconds = Date.now() / 1000) {
  try {
    const command = commandInput(input, nowSeconds);
    if (!storage?.sql || typeof storage.sql.exec !== 'function' || typeof storage.transactionSync !== 'function') {
      throw new Error('Unavailable storage');
    }
    const sql = storage.sql;
    initialize(sql);
    // Commit expiry separately so a later rejected update cannot restore data
    // that has reached its retention deadline.
    const cleanup = storage.transactionSync(() => sql.exec('DELETE FROM cases WHERE created_at <= ?', nowSeconds - CASE_TTL_SECONDS).rowsWritten);
    if (command.op === 'cleanup') return cleanup;
    return storage.transactionSync(() => {
      const owner = command.owner_hash;
      const id = command.case?.id ?? command.id;
      if (command.op === 'get') {
        const row = sql.exec('SELECT payload FROM cases WHERE id = ? AND owner_hash = ?', id, owner).toArray()[0];
        return row ? JSON.parse(row.payload) : null;
      }
      if (command.op === 'delete') {
        return sql.exec('DELETE FROM cases WHERE id = ? AND owner_hash = ?', id, owner).rowsWritten > 0;
      }
      const item = command.case;
      if (command.op === 'create') {
        // Both count and insertion share the same transaction, including calls
        // from another container; no in-memory quota state is trusted.
        const count = sql.exec('SELECT COUNT(*) AS count FROM cases WHERE owner_hash = ?', owner).toArray()[0].count;
        if (count >= MAX_CASES_PER_OWNER) {
          throw new CaseStoreError('CASE_LIMIT', '暫存案件數量已達上限，請先清除不再使用的案件。', 429);
        }
        if (sql.exec('SELECT id FROM cases WHERE id = ?', id).toArray().length) {
          throw new CaseStoreError('CASE_EXISTS', '案件識別碼已存在。', 409);
        }
        sql.exec('INSERT INTO cases(id, owner_hash, created_at, payload) VALUES (?, ?, ?, ?)', id, owner, createdTimestamp(item.created_at), JSON.stringify(item));
        return item;
      }
      const row = sql.exec('SELECT payload FROM cases WHERE id = ? AND owner_hash = ?', id, owner).toArray()[0];
      if (!row) throw new CaseStoreError('CASE_NOT_FOUND', '查無案件，或案件已清除。', 404);
      const previous = JSON.parse(row.payload);
      if (Object.hasOwn(previous, 'revision') || Object.hasOwn(item, 'revision') || Object.hasOwn(command, 'expected_revision')) {
        if (!Object.hasOwn(command, 'expected_revision')) invalid();
        if (previous.revision !== command.expected_revision || item.revision !== command.expected_revision + 1) {
          throw new CaseStoreError('CASE_CONFLICT', '案件已更新，請重新載入後再試。', 409);
        }
      }
      // Edits may never renew the original retention deadline.
      item.created_at = previous.created_at;
      sql.exec('UPDATE cases SET payload = ? WHERE id = ? AND owner_hash = ?', JSON.stringify(item), id, owner);
      return item;
    });
  } catch (error) {
    if (error instanceof CaseStoreError) throw error;
    // Never expose database errors, case payloads, credentials or SQL text.
    throw new CaseStoreError('CASE_STORE_UNAVAILABLE', '案件暫存服務暫時無法使用，請稍後再試。', 503);
  }
}
