import test from 'node:test';
import assert from 'node:assert/strict';
import { createClaimService } from '../src/services/index.js';
import { ApiClaimService } from '../src/services/api-claim-service.js';
import { consumeRuntimeKey } from '../src/runtime-key.js';

const syntheticKey = () => ['sk', 'or', 'v1', 'a'.repeat(64)].join('-');
const CASE = '12345678-1234-4234-8234-123456789abc';
const JOB = '87654321-1234-4234-9234-123456789abc';
const origin = 'http://localhost';
const result = { case: { id: CASE, documents: [], messages: [] }, response: { message: '合成傳輸回覆' } };

function runtime(key = syntheticKey()) {
  const location = new URL(origin + (key === null ? '/' : '/?key=' + key));
  return consumeRuntimeKey(location, { state: null, replaceState(_state, _title, url) { location.href = origin + url; } });
}

test('真正 HTTP adapter 只在 health 和對話 POST 附加執行期標頭，輪詢與 CRUD／OCR 不帶金鑰', async () => {
  const requests = [];
  const key = runtime();
  const service = createClaimService({ mode: 'api', runtimeHeadersFor: key.headersFor, messagePollInterval: 1, fetchImpl: async (url, options) => {
    const request = new Request(origin + url, options);
    requests.push(request);
    if (request.method === 'POST' && url.endsWith('/message-jobs')) return Response.json({ id: JOB, status: 'pending' }, { status: 202 });
    if (request.method === 'GET' && url.endsWith('/' + JOB)) return Response.json({ id: JOB, status: 'succeeded', result });
    return Response.json({ ok: true });
  } });

  await service.health();
  assert.deepEqual(await service.sendMessage(CASE, '合成問題', { document_id: 'application' }), result);
  await service.getClaimTypes();
  await service.getLibrary({ query: '申請書' });
  await service.getFaq();
  await service.getProduct('SYNTHETIC');
  await service.createCase({ entry_path: 'guided' });
  await service.getCase(CASE);
  await service.updateCase(CASE, { conditions: { cause: 'illness' } });
  await service.getChecklist(CASE);
  await service.updateDocument(CASE, 'application', { status: 'uploaded' });
  await service.analyzeDocument(CASE, 'application', new File(['synthetic'], 'synthetic.png', { type: 'image/png' }));
  await service.getSource('cardif-claims');
  await service.deleteCase(CASE);

  assert.equal(requests[0].headers.get('X-OpenRouter-Key'), syntheticKey());
  assert.equal(requests[1].headers.get('X-OpenRouter-Key'), syntheticKey());
  for (const request of requests.slice(2)) assert.equal(request.headers.has('X-OpenRouter-Key'), false, request.method + ' ' + request.url);
  assert.deepEqual(await requests[1].clone().json(), { message: '合成問題', document_id: 'application' });
  for (const request of requests) {
    assert.equal(request.url.includes(syntheticKey()), false);
    assert.equal((await request.clone().text()).includes(syntheticKey()), false);
    assert.equal(request.mode, 'same-origin');
    assert.equal(request.credentials, 'same-origin');
    assert.equal(request.redirect, 'error');
  }
  assert.equal(JSON.stringify(service).includes(syntheticKey()), false);
});

test('adapter 對最終請求 URL 評估標頭，不將相似或重導向目標當作必要端點', async () => {
  const requests = [];
  const evaluated = [];
  const key = runtime();
  const service = new ApiClaimService({ baseUrl: '/other-api', runtimeHeadersFor: (url, method) => {
    evaluated.push([url, method]);
    return key.headersFor(url, method);
  }, fetchImpl: async (url, options) => {
    requests.push(new Request(origin + url, options));
    return Response.json({ ok: true });
  } });
  await service.health();
  await service.request(`/cases/${CASE}/messages`, { method: 'POST', json: { message: '合成問題' } });
  assert.deepEqual(evaluated, [['/other-api/health', 'GET'], [`/other-api/cases/${CASE}/messages`, 'POST']]);
  assert.ok(requests.every(request => !request.headers.has('X-OpenRouter-Key')));

  const redirected = new ApiClaimService({ runtimeHeadersFor: key.headersFor, fetchImpl: async (_url, options) => {
    assert.equal(options.redirect, 'error');
    throw new TypeError('synthetic redirect rejection');
  } });
  await assert.rejects(redirected.health(), error => error.code === 'NETWORK_ERROR' && !String(error).includes(syntheticKey()));
});

test('缺少或遭拒的金鑰保留後端錯誤、不輪詢、不重試或改用 Mock', async () => {
  for (const [raw, code, status] of [[null, 'KEY_REQUIRED', 401], ['invalid-demo-value', 'KEY_INVALID', 422]]) {
    let calls = 0;
    const service = createClaimService({ mode: 'api', runtimeHeadersFor: runtime(raw).headersFor, fetchImpl: async (_url, options) => {
      calls++;
      assert.equal(new Headers(options.headers).has('X-OpenRouter-Key'), false);
      return Response.json({ error: { code, message: '請使用有效的展示金鑰。' } }, { status });
    } });
    await assert.rejects(service.sendMessage(CASE, '合成問題'), error => error.code === code && error.status === status && !JSON.stringify(error).includes(syntheticKey()));
    assert.equal(calls, 1);
    assert.equal(service.mode, 'api');
  }
});

test('Mock 不取用執行期標頭，錯誤 callback 型別在 API 建構時明確拒絕', async () => {
  const service = createClaimService({ mode: 'mock', delay: 0, storage: null, runtimeHeadersFor: () => { throw new Error('Mock 不得讀取金鑰'); } });
  assert.equal((await service.health()).service_mode, 'mock');
  assert.throws(() => new ApiClaimService({ runtimeHeadersFor: 'not-a-function' }), TypeError);
});
