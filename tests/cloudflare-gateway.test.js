import test from 'node:test';
import assert from 'node:assert/strict';
import {routeRequest} from '../cloudflare/gateway.js';

const origin='https://claim-demo.example.workers.dev';
const token='synthetic-internal-token-for-tests';
function services(overrides={}){
  return {storeToken:token,assetFetch:async()=>new Response('static-demo'),apiFetch:async()=>new Response('{"status":"ok"}',{headers:{'Content-Type':'application/json','Set-Cookie':'claim_session=synthetic; Path=/; Secure; HttpOnly; SameSite=strict'}}),storeCall:async()=>({result:null}),...overrides};
}
test('static response sets no-referrer and CSP without reflecting URL key',async()=>{
  const response=await routeRequest(new Request(origin+'/?key=synthetic-demo-key'),services());
  assert.equal(response.status,200);
  assert.equal(response.headers.get('referrer-policy'),'no-referrer');
  assert.equal(response.headers.get('cache-control'),'no-store');
  assert.match(response.headers.get('content-security-policy'),/script-src 'self'/);
  assert.equal(await response.text(),'static-demo');
});
test('API stays same-origin, uncached, and retains owner cookie',async()=>{
  const response=await routeRequest(new Request(origin+'/api/v1/health'),services());
  assert.equal(response.status,200);
  assert.equal(response.headers.get('cache-control'),'no-store');
  assert.match(response.headers.get('set-cookie'),/Secure; HttpOnly; SameSite=strict/);
});
for(const headers of [{Origin:'https://evil.example'},{'Sec-Fetch-Site':'cross-site'}])test('cross-site API is refused before container invocation '+JSON.stringify(headers),async()=>{
  let calls=0;
  const response=await routeRequest(new Request(origin+'/api/v1/cases',{method:'POST',headers}),services({apiFetch:()=>{calls++;}}));
  assert.equal(response.status,403);assert.equal(calls,0);
});
test('API rejects URL credentials without echo or forwarding',async()=>{
  let calls=0;const response=await routeRequest(new Request(origin+'/api/v1/health?key=not-a-real-key'),services({apiFetch:()=>{calls++;}}));
  assert.equal(response.status,422);assert.equal(calls,0);assert.doesNotMatch(await response.text(),/not-a-real-key/);
});
for(const path of ['/.env','/.local/cases.sqlite3','/.git/config','/backend/app/main.py','/src/app.js','/__internal/unknown'])test('private path is not exposed '+path,async()=>{
  let calls=0;const response=await routeRequest(new Request(origin+path),services({assetFetch:()=>{calls++;}}));
  assert.equal(response.status,404);assert.equal(calls,0);
});
test('internal store requires correct private header and never reads token from query',async()=>{
  for(const headers of [{},{Authorization:'Bearer wrong'}]){
    const response=await routeRequest(new Request(origin+'/__internal/cases?token='+token,{method:'POST',headers,body:'{}'}),services({storeCall:()=>assert.fail('unauthorized store call')}));
    assert.equal(response.status,404);assert.doesNotMatch(await response.text(),new RegExp(token));
  }
});
test('authorized store passes only parsed command and translates controlled errors',async()=>{
  const command={op:'cleanup'};let received;
  let response=await routeRequest(new Request(origin+'/__internal/cases',{method:'POST',headers:{Authorization:'Bearer '+token},body:JSON.stringify(command)}),services({storeCall:async value=>{received=value;return {result:2};}}));
  assert.equal(response.status,200);assert.deepEqual(await response.json(),{result:2});assert.deepEqual(received,command);
  response=await routeRequest(new Request(origin+'/__internal/cases',{method:'POST',headers:{Authorization:'Bearer '+token},body:'{}'}),services({storeCall:async()=>({error:{code:'CASE_CONFLICT',message:'案件已更新。',status:409}})}));
  assert.equal(response.status,409);assert.equal((await response.json()).error.code,'CASE_CONFLICT');
});
test('malformed or excessive internal bodies fail without calling storage',async()=>{
  for(const body of ['{bad','a'.repeat(1048577)]){
    const response=await routeRequest(new Request(origin+'/__internal/cases',{method:'POST',headers:{Authorization:'Bearer '+token},body}),services({storeCall:()=>assert.fail('invalid body forwarded')}));
    assert.ok([413,422].includes(response.status));assert.equal(response.headers.get('cache-control'),'no-store');
  }
});
test('backend failure details never reach public response',async()=>{
  const response=await routeRequest(new Request(origin+'/api/v1/health'),services({apiFetch:()=>{throw new Error(token);}}));
  assert.equal(response.status,503);assert.doesNotMatch(await response.text(),new RegExp(token));
});

test('backend lifecycle status is private, read-only and uncached',async()=>{
  const status={running:true,boot_id:'dbf84bee-6125-447e-b173-b0976aa03bf0',image_matches:true};
  let calls=0;
  const response=await routeRequest(new Request(origin+'/__internal/backend',{headers:{Authorization:'Bearer '+token}}),services({backendStatus:async()=>{calls++;return {...status,secret:token};}}));
  assert.equal(response.status,200);assert.deepEqual(await response.json(),status);
  assert.equal(response.headers.get('cache-control'),'no-store');assert.equal(calls,1);
});

test('lifecycle endpoint rejects unauthorized methods and credential query',async()=>{
  for(const [suffix,method,header] of [['','GET',''],['','GET','Bearer wrong'],['?token='+token,'GET','Bearer '+token],['','POST','Bearer '+token]]){
    const response=await routeRequest(new Request(origin+'/__internal/backend'+suffix,{method,headers:{Authorization:header}}),services({backendStatus:()=>assert.fail('unauthorized lifecycle call')}));
    assert.equal(response.status,404);assert.doesNotMatch(await response.text(),new RegExp(token));
  }
});

test('invalid lifecycle metadata cannot leak secrets',async()=>{
  for(const status of [{running:true,boot_id:token,image_matches:true},{running:true,boot_id:'dbf84bee-6125-447e-b173-b0976aa03bf0\n',image_matches:true},{running:'true',boot_id:null,image_matches:false},null]){
    const response=await routeRequest(new Request(origin+'/__internal/backend',{headers:{Authorization:'Bearer '+token}}),services({backendStatus:async()=>status}));
    assert.equal(response.status,503);assert.doesNotMatch(await response.text(),new RegExp(token));
  }
});
