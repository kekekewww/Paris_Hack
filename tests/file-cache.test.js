import test from 'node:test';
import assert from 'node:assert/strict';
import {fingerprintFile, fileMatchesMetadata, FilePreviewCache} from '../src/file-cache.js';

const file = (contents='abc', name='synthetic.pdf') => new File([contents], name, {type:'application/pdf',lastModified:1});
const abcHash='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

test('fingerprints hash all bytes and do not rely on filename or timestamps',async()=>{
  assert.equal(await fingerprintFile(file()),abcHash);
  assert.equal(await fingerprintFile(file('abc','another.pdf')),abcHash);
  assert.notEqual(await fingerprintFile(file('abd')),abcHash);
  const a=new Uint8Array(8192), b=new Uint8Array(a);b[b.length-1]=1;
  assert.notEqual(await fingerprintFile(file(a)),await fingerprintFile(file(b)));
});

test('reselected originals match the server SHA256 instead of filename or metadata',async()=>{
  const original=file(),different=file('abd');
  const metadata={name:original.name,size:original.size,type:original.type,sha256:abcHash};
  assert.equal(fileMatchesMetadata(original,await fingerprintFile(original),metadata),true);
  assert.equal(fileMatchesMetadata(different,await fingerprintFile(different),metadata),false);
  assert.equal(fileMatchesMetadata(original,abcHash,{...metadata,sha256:undefined}),false);
  assert.equal(fileMatchesMetadata(original,'invalid',metadata),false);
});

test('cache keeps original File per case document and analysis version only in memory',()=>{
  const cache=new FilePreviewCache(),original=file();
  assert.equal(cache.set('case-a','application','analysis-1',original,abcHash),true);
  assert.deepEqual(cache.get('case-a','application','analysis-1'),{file:original,fingerprint:abcHash});
  assert.equal(cache.get('case-a','application','analysis-2'),null);
  assert.equal(cache.get('case-b','application','analysis-1'),null);
  assert.equal(new FilePreviewCache().get('case-a','application','analysis-1'),null);
});

test('new analysis and replacement files remove the old document version',()=>{
  const cache=new FilePreviewCache(),first=file(),second=file('def');
  cache.set('a','application','v1',first,abcHash);
  cache.set('a','application','v2',second,'a'.repeat(64));
  assert.equal(cache.get('a','application','v1'),null);
  assert.equal(cache.get('a','application','v2').file,second);
  cache.clearDocument('a','application');
  assert.equal(cache.get('a','application','v2'),null);
});

test('bounded cache evicts least recently used files and rejects oversized entries',()=>{
  const cache=new FilePreviewCache({maxBytes:6,maxFileBytes:4});
  cache.set('a','one','v1',file('123'),'1'.repeat(64));
  cache.set('a','two','v1',file('456'),'2'.repeat(64));
  cache.get('a','one','v1');
  cache.set('b','three','v1',file('789'),'3'.repeat(64));
  assert.equal(cache.get('a','two','v1'),null);
  assert.ok(cache.get('a','one','v1'));
  assert.equal(cache.set('a','huge','v1',file('12345'),'4'.repeat(64)),false);
  assert.equal(cache.set('a','empty','v1',file(''),'5'.repeat(64)),false);
  assert.equal(cache.totalBytes,6);
  assert.equal(cache.size,2);
});

test('delete case clears only its files while clear releases every cached original',()=>{
  const cache=new FilePreviewCache();
  cache.set('a','x','v1',file(),'1'.repeat(64));
  cache.set('b','x','v1',file(),'2'.repeat(64));
  cache.clearCase('a');
  assert.equal(cache.get('a','x','v1'),null);
  assert.ok(cache.get('b','x','v1'));
  cache.clear();
  assert.equal(cache.get('b','x','v1'),null);
  assert.equal(cache.totalBytes,0);
  assert.equal(cache.size,0);
});

test('ambiguous delimiter keys and invalid entries cannot leak another document',()=>{
  const cache=new FilePreviewCache();
  cache.set('case:a','b','c',file(),abcHash);
  assert.equal(cache.get('case','a:b','c'),null);
  for(const args of [['','b','c',file(),abcHash],['a','b','',file(),abcHash],['a','b','c',file(),'not-a-hash'],['a','b','c',{},abcHash]])assert.equal(cache.set(...args),false);
  assert.equal(cache.size,1);
});

test('fingerprinting refuses empty and over-limit input before reading bytes',async()=>{
  await assert.rejects(fingerprintFile(file('')),/空白/);
  let read=false;
  await assert.rejects(fingerprintFile({name:'synthetic.pdf',size:10*1024*1024+1,arrayBuffer(){read=true;throw new Error('must not read')}}),/10 MB/);
  assert.equal(read,false);
});
