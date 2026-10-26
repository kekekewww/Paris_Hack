const FILE_LIMIT=10*1024*1024;
const hashPattern=/^[a-f0-9]{64}$/;
const validFile=file=>!!file&&typeof file.name==='string'&&typeof file.arrayBuffer==='function'&&Number.isSafeInteger(file.size)&&file.size>0;
const validId=value=>typeof value==='string'&&value.length>0;

// 原檔只由此分頁暫存；摘要不包含姓名、檔名或文件內容。
export async function fingerprintFile(file) {
  if(!file||!Number.isSafeInteger(file.size)||file.size===0)throw new Error('檔案是空白的，請重新選擇。');
  if(file.size>FILE_LIMIT)throw new Error('檔案不可超過 10 MB，請壓縮後再選擇。');
  if(!validFile(file))throw new Error('無法讀取這份文件，請重新選擇。');
  if(!globalThis.crypto?.subtle)throw new Error('此瀏覽器無法安全核對原始文件，請重新分析。');
  const bytes=await file.arrayBuffer();
  if(bytes.byteLength!==file.size)throw new Error('文件內容已變更，請重新選擇。');
  const digest=await globalThis.crypto.subtle.digest('SHA-256',bytes);
  return [...new Uint8Array(digest)].map(value=>value.toString(16).padStart(2,'0')).join('');
}

export function fileMatchesMetadata(file,fingerprint,metadata) {
  return validFile(file)&&hashPattern.test(fingerprint)&&hashPattern.test(metadata?.sha256)&&fingerprint===metadata.sha256;
}

// 不建立Object URL、不寫入任何Storage；呼叫端負責釋放預覽URL。
export class FilePreviewCache {
  #entries=new Map();
  #totalBytes=0;
  #maxBytes;
  #maxFileBytes;

  constructor({maxBytes=30*1024*1024,maxFileBytes=FILE_LIMIT}={}) {
    if(!Number.isSafeInteger(maxBytes)||maxBytes<1||!Number.isSafeInteger(maxFileBytes)||maxFileBytes<1)throw new TypeError('暫存容量必須為正整數。');
    this.#maxBytes=maxBytes;
    this.#maxFileBytes=Math.min(maxFileBytes,FILE_LIMIT);
  }

  get size(){return this.#entries.size}
  get totalBytes(){return this.#totalBytes}

  get(caseId,docId,analysisId) {
    const key=JSON.stringify([caseId,docId,analysisId]);
    const entry=this.#entries.get(key);
    if(!entry)return null;
    this.#entries.delete(key);
    this.#entries.set(key,entry);
    return {file:entry.file,fingerprint:entry.fingerprint};
  }

  set(caseId,docId,analysisId,file,fingerprint) {
    if(![caseId,docId,analysisId].every(validId)||!validFile(file)||!hashPattern.test(fingerprint)||file.size>this.#maxFileBytes||file.size>this.#maxBytes)return false;
    this.clearDocument(caseId,docId);
    while(this.#totalBytes+file.size>this.#maxBytes)this.#remove(this.#entries.keys().next().value);
    this.#entries.set(JSON.stringify([caseId,docId,analysisId]),{caseId,docId,analysisId,file,fingerprint});
    this.#totalBytes+=file.size;
    return true;
  }

  #remove(key) {
    const entry=this.#entries.get(key);
    if(entry){this.#totalBytes-=entry.file.size;this.#entries.delete(key)}
  }

  clearDocument(caseId,docId) {
    for(const [key,entry] of this.#entries)if(entry.caseId===caseId&&entry.docId===docId)this.#remove(key);
  }

  clearCase(caseId) {
    for(const [key,entry] of this.#entries)if(entry.caseId===caseId)this.#remove(key);
  }

  clear(){this.#entries.clear();this.#totalBytes=0}
}
