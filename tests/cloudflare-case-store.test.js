import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { executeCaseCommand } from '../cloudflare/case-store.js';

const NOW = Date.parse('2026-10-30T12:00:00Z') / 1000;
const OWNER = 'a'.repeat(64);
const OTHER = 'b'.repeat(64);

function database(path = ':memory:') {
  const db = new DatabaseSync(path);
  db.exec('PRAGMA busy_timeout=5000');
  return {
    db,
    sql: {
      exec(query, ...params) {
        const statement = db.prepare(query);
        if (statement.columns().length) {
          const rows = statement.all(...params);
          return { toArray: () => rows, rowsWritten: 0 };
        }
        const result = statement.run(...params);
        return { toArray: () => [], rowsWritten: result.changes };
      },
    },
    transactionSync(callback) {
      db.exec('BEGIN IMMEDIATE');
      try {
        const result = callback();
        db.exec('COMMIT');
        return result;
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
    },
  };
}

function fixture(t, path) {
  const storage = database(path);
  t.after(() => storage.db.close());
  return storage;
}

function item(overrides = {}) {
  return {
    id: randomUUID(), entry_path: 'direct', claim_type_id: 'inpatient',
    conditions: {
      cause: 'unknown', surgery: 'unknown', receipt_type: 'unknown',
      payment_method: 'unknown', first_claim: 'unknown',
      diagnosis_has_surgery_details: 'unknown', pathology_required_for_condition: 'unknown',
      insurer_requested_medical_authorization: 'unknown', insurer_requested_nhi_request: 'unknown',
    },
    details: {}, dialogue_state: {}, revision: 0,
    documents: [], messages: [],
    created_at: '2026-10-30T12:00:00+00:00',
    updated_at: '2026-10-30T12:00:00+00:00',
    ...overrides,
  };
}

function run(storage, op, fields = {}, owner = OWNER, now = NOW) {
  return executeCaseCommand(storage, { op, ...(op === 'cleanup' ? {} : { owner_hash: owner }), ...fields }, now);
}

function rejects(callback, code = 'VALIDATION_ERROR', status = 422) {
  assert.throws(callback, error => error.code === code && error.status === status);
}

test('created structured case can be loaded with independent returned objects', t => {
  const storage = fixture(t);
  const original = item();
  const created = run(storage, 'create', { case: original });
  original.details.diagnosis_name = 'changed caller';
  created.conditions.cause = 'accident';
  const loaded = run(storage, 'get', { id: created.id });
  assert.equal(loaded.id, created.id);
  assert.deepEqual(loaded.details, {});
  assert.equal(loaded.conditions.cause, 'unknown');
  assert.equal(loaded.conditions.insurer_requested_medical_authorization, 'unknown');
  loaded.messages.push({ content: 'caller only' });
  assert.deepEqual(run(storage, 'get', { id: created.id }).messages, []);
});

test('case remains available after reopening the same SQLite database', t => {
  const directory = mkdtempSync(join(tmpdir(), 'claim-do-'));
  const path = join(directory, 'cases.sqlite3');
  const first = database(path);
  const created = run(first, 'create', { case: item() });
  first.db.close();
  const reopened = fixture(t, path);
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  assert.equal(run(reopened, 'get', { id: created.id }).claim_type_id, 'inpatient');
});

test('another owner cannot load, update or delete an existing case', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  assert.equal(run(storage, 'get', { id: created.id }, OTHER), null);
  assert.equal(run(storage, 'delete', { id: created.id }, OTHER), false);
  rejects(() => run(storage, 'save', { case: { ...created, revision: 1 }, expected_revision: 0 }, OTHER), 'CASE_NOT_FOUND', 404);
  assert.equal(run(storage, 'get', { id: created.id }).revision, 0);
});

test('delete reports existence and makes a case inaccessible', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  assert.equal(run(storage, 'delete', { id: created.id }), true);
  assert.equal(run(storage, 'delete', { id: created.id }), false);
  assert.equal(run(storage, 'get', { id: created.id }), null);
});

test('duplicate identifiers return a stable conflict without replacing data', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  rejects(() => run(storage, 'create', { case: { ...created, claim_type_id: 'outpatient' } }, OTHER), 'CASE_EXISTS', 409);
  assert.equal(run(storage, 'get', { id: created.id }).claim_type_id, 'inpatient');
});

test('twenty-case quota is per owner and deletion releases a slot', t => {
  const storage = fixture(t);
  const cases = Array.from({ length: 20 }, () => run(storage, 'create', { case: item() }));
  rejects(() => run(storage, 'create', { case: item() }), 'CASE_LIMIT', 429);
  assert.ok(run(storage, 'create', { case: item() }, OTHER).id);
  run(storage, 'delete', { id: cases[0].id });
  assert.ok(run(storage, 'create', { case: item() }).id);
});

test('cleanup removes all owners at the exact twenty-four-hour boundary', t => {
  const storage = fixture(t);
  const boundary = item({ created_at: '2026-10-29T12:00:00Z' });
  const fresh = item({ created_at: '2026-10-29T12:00:00.000001+00:00' });
  run(storage, 'create', { case: boundary }, OWNER, NOW - 1);
  run(storage, 'create', { case: fresh }, OTHER, NOW - 1);
  assert.equal(run(storage, 'cleanup'), 1);
  assert.equal(run(storage, 'get', { id: boundary.id }), null);
  assert.equal(run(storage, 'get', { id: fresh.id }, OTHER).id, fresh.id);
});

test('ordinary reads also expire cases and cleanup returns zero afterward', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  assert.equal(run(storage, 'get', { id: created.id }, OWNER, NOW + 86400), null);
  assert.equal(run(storage, 'cleanup', {}, OWNER, NOW + 86400), 0);
});

test('expiry releases the owner quota before a new case is created', t => {
  const storage = fixture(t);
  for (let index = 0; index < 20; index++) run(storage, 'create', { case: item() });
  assert.ok(run(storage, 'create', { case: item({ created_at: '2026-10-31T12:00:00Z' }) }, OWNER, NOW + 86400).id);
});

test('save preserves original creation time and cannot extend retention', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  const saved = run(storage, 'save', { case: { ...created, created_at: '2026-11-20T12:00:00Z', revision: 1 }, expected_revision: 0 }, OWNER, NOW + 86399);
  assert.equal(saved.created_at, '2026-10-30T12:00:00+00:00');
  assert.equal(saved.revision, 1);
  assert.equal(run(storage, 'get', { id: created.id }, OWNER, NOW + 86400), null);
});

test('missing and expired cases cannot be resurrected with save', t => {
  const storage = fixture(t);
  rejects(() => run(storage, 'save', { case: item({ revision: 1 }), expected_revision: 0 }), 'CASE_NOT_FOUND', 404);
  const created = run(storage, 'create', { case: item() });
  rejects(() => run(storage, 'save', { case: { ...created, revision: 1 }, expected_revision: 0 }, OWNER, NOW + 86400), 'CASE_NOT_FOUND', 404);
  assert.equal(storage.db.prepare('SELECT COUNT(*) AS count FROM cases').get().count, 0);
});

test('two updates from the same old revision cannot overwrite each other', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  run(storage, 'save', { case: { ...created, revision: 1, claim_type_id: 'outpatient' }, expected_revision: 0 });
  rejects(() => run(storage, 'save', { case: { ...created, revision: 1, claim_type_id: 'critical_illness' }, expected_revision: 0 }), 'CASE_CONFLICT', 409);
  assert.equal(run(storage, 'get', { id: created.id }).claim_type_id, 'outpatient');
});

test('save rejects revision jumps and malformed expected revisions', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  rejects(() => run(storage, 'save', { case: { ...created, revision: 5 }, expected_revision: 0 }), 'CASE_CONFLICT', 409);
  for (const expected_revision of [-1, true, 0.5, '0', null]) {
    rejects(() => run(storage, 'save', { case: { ...created, revision: 1 }, expected_revision }));
  }
  assert.equal(run(storage, 'get', { id: created.id }).revision, 0);
});

test('save requires CAS for a revisioned case to prevent a bypass', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  rejects(() => run(storage, 'save', { case: { ...created, revision: 1 } }));
});

test('file metadata is retained without raw file bytes', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item({ documents: [{ file: { name: '合成.pdf', type: 'application/pdf', size: 123, sha256: 'c'.repeat(64) } }] }) });
  assert.equal(run(storage, 'get', { id: created.id }).documents[0].file.name, '合成.pdf');
});

test('full conditions for all direct claim types retain the medical-authorization tri-state through create and save', t => {
  const storage = fixture(t);
  for (const claim_type_id of ['inpatient', 'outpatient', 'critical_illness']) {
    for (const answer of ['yes', 'no', 'unknown']) {
      const original = item({ claim_type_id });
      original.conditions.insurer_requested_medical_authorization = answer;
      const created = run(storage, 'create', { case: original });
      assert.equal(run(storage, 'get', { id: created.id }).conditions.insurer_requested_medical_authorization, answer);
      const saved = run(storage, 'save', { case: { ...created, revision: 1 }, expected_revision: 0 });
      assert.equal(saved.conditions.insurer_requested_medical_authorization, answer);
      assert.equal(saved.claim_type_id, claim_type_id);
    }
  }
});

test('medical-authorization condition rejects every non-enum value without saving a case', t => {
  const storage = fixture(t);
  run(storage, 'cleanup');
  for (const answer of ['synthetic-credential', 'Bearer synthetic-token', null, {}, ['yes'], true, 0, 'YES', '']) {
    const original = item();
    original.conditions.insurer_requested_medical_authorization = answer;
    rejects(() => run(storage, 'create', { case: original }));
  }
  assert.equal(storage.db.prepare('SELECT COUNT(*) AS count FROM cases').get().count, 0);
});

test('the medical-authorization exception never permits other authorization or credential field names', t => {
  const storage = fixture(t);
  for (const field of ['authorization', 'medical_authorization', 'other_medical_authorization', 'insurer_requested_medical_authorization_token', 'insurer_requested_medical_authorization_secret']) {
    const original = item();
    original.conditions[field] = 'yes';
    rejects(() => run(storage, 'create', { case: original }));
  }
});

test('raw document fields and credential spelling variants are rejected at any depth', t => {
  const storage = fixture(t);
  run(storage, 'cleanup');
  const fields = ['raw_file', 'file_bytes', 'raw_text', 'BASE64', 'data-url', 'blob', 'api_key', 'apiKey', 'openrouter_api_key', 'openai_api_key', 'provider_api_key', 'gemini_api_key', 'x-api-key', 'bearer_token', 'session_token', 'shared_secret', 'authorization', 'access_token', 'private_key', 'password', 'x-openrouter-key', 'case_store_token', 'key'];
  for (const field of fields) {
    rejects(() => run(storage, 'create', { case: item({ documents: [{ analysis: { [field]: 'synthetic-rejected' } }] }) }));
  }
  assert.equal(storage.db.prepare('SELECT COUNT(*) AS count FROM cases').get().count, 0);
});

test('file objects reject extra content fields and non-metadata types', t => {
  const storage = fixture(t);
  for (const file of ['data:text/plain,raw', ['raw'], { name: 'x', content: 'raw' }, { name: 'x', size: -1 }, { name: 'x', size: 1, type: 'text/plain', sha256: 'invalid' }]) {
    rejects(() => run(storage, 'create', { case: item({ documents: [{ file }] }) }));
  }
});

test('invalid operation shapes and unknown command fields are rejected', t => {
  const storage = fixture(t);
  for (const command of [null, [], 'get', {}, { op: 'list', owner_hash: OWNER }, { op: 'cleanup', owner_hash: OWNER }, { op: 'get', owner_hash: OWNER, id: randomUUID(), token: 'unexpected' }]) {
    rejects(() => executeCaseCommand(storage, command, NOW));
  }
});

test('an array operation cannot coerce into a save command and alter a case', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item() });
  rejects(() => executeCaseCommand(storage, {
    op: ['save'], owner_hash: OWNER,
    case: { ...created, revision: 1, claim_type_id: 'outpatient' }, expected_revision: 0,
  }, NOW));
  assert.equal(run(storage, 'get', { id: created.id }).revision, 0);
});

test('malformed owner hashes and SQL-injection identifiers cannot access stored data', t => {
  const storage = fixture(t);
  for (const owner of ['', 'a'.repeat(63), 'A'.repeat(64), `x' OR 1=1 --`, null]) {
    rejects(() => run(storage, 'get', { id: randomUUID() }, owner));
  }
  for (const id of ['', 'not-uuid', `x' OR 1=1 --`, null, 3]) {
    rejects(() => run(storage, 'delete', { id }));
  }
});

test('invalid calendar dates and dates without a timezone cannot change retention', t => {
  const storage = fixture(t);
  for (const created_at of ['2026-02-30T12:00:00Z', '2026-10-30T12:00:00', 'not-date', null, '2026-10-30T12:00:00+25:00']) {
    rejects(() => run(storage, 'create', { case: item({ created_at }) }));
  }
});

test('offset-aware creation times expire at the same UTC instant', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: item({ created_at: '2026-10-30T20:00:00+08:00' }) });
  assert.ok(run(storage, 'get', { id: created.id }, OWNER, NOW + 86399));
  assert.equal(run(storage, 'get', { id: created.id }, OWNER, NOW + 86400), null);
});

test('non-JSON values are rejected rather than silently corrupted', t => {
  const storage = fixture(t);
  const circular = {}; circular.next = circular;
  for (const value of [NaN, Infinity, undefined, 1n, () => 1, new Uint8Array([1]), new Date(), circular]) {
    rejects(() => run(storage, 'create', { case: item({ details: { value } }) }));
  }
});

test('prototype-sensitive JSON fields cannot be persisted', t => {
  const storage = fixture(t);
  for (const field of ['__proto__', 'constructor', 'prototype']) {
    const details = JSON.parse(`{"${field}":{"synthetic":"rejected"}}`);
    rejects(() => run(storage, 'create', { case: item({ details }) }));
  }
});

test('omitted creation defaults are generated while explicit null identifiers are rejected', t => {
  const storage = fixture(t);
  const created = run(storage, 'create', { case: { revision: 0, documents: [], messages: [] } });
  assert.match(created.id, /^[a-f0-9-]{36}$/);
  assert.equal(created.created_at, '2026-10-30T12:00:00.000Z');
  assert.equal(created.updated_at, '2026-10-30T12:00:00.000Z');
  rejects(() => run(storage, 'create', { case: item({ id: null }) }));
});

test('excessive nesting and oversized UTF-8 payloads are rejected', t => {
  const storage = fixture(t);
  let nested = {};
  for (let index = 0; index < 40; index++) nested = { nested };
  rejects(() => run(storage, 'create', { case: item({ details: nested }) }));
  rejects(() => run(storage, 'create', { case: item({ messages: [{ content: '中'.repeat(400000) }] }) }), 'PAYLOAD_TOO_LARGE', 413);
});

test('SQL failures return a sanitized storage error and leave no partial case', t => {
  const storage = fixture(t);
  run(storage, 'cleanup');
  storage.db.exec("CREATE TRIGGER reject_cases BEFORE INSERT ON cases BEGIN SELECT RAISE(ABORT, 'sensitive database diagnostic'); END");
  assert.throws(() => run(storage, 'create', { case: item() }), error => {
    assert.equal(error.code, 'CASE_STORE_UNAVAILABLE');
    assert.equal(error.status, 503);
    assert.doesNotMatch(error.message, /sensitive|diagnostic|SQLITE/);
    return true;
  });
  assert.equal(storage.db.prepare('SELECT COUNT(*) AS count FROM cases').get().count, 0);
});
