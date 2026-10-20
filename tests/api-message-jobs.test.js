import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiClaimService } from '../src/services/api-claim-service.js';

const JOB = '12345678-1234-4234-8234-123456789abc';
const OTHER_JOB = '87654321-1234-4234-9234-123456789abc';
const CASE = 'synthetic case';
const answer = (id = CASE) => ({
  case: { id, entry_path: 'guided', claim_type_id: null, conditions: {}, documents: [], messages: [], created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z' },
  response: { response_type: 'clarification', message: '合成對話回覆', suggested_claim_types: [], missing_information: ['care_setting'], source_references: [], proposed_case_updates: {}, requires_human_review: true, provider: 'openai_compatible', is_simulated: false },
});
const accepted = () => Response.json({ id: JOB, status: 'pending' }, { status: 202 });
const pending = () => Response.json({ id: JOB, status: 'pending' });
const succeeded = (result = answer()) => Response.json({ id: JOB, status: 'succeeded', result });
const flush = async () => { for (let index = 0; index < 30; index++) await Promise.resolve(); };
const advance = async (t, milliseconds) => { t.mock.timers.tick(milliseconds); await flush(); };
const observe = promise => {
  const state = { status: 'pending' };
  promise.then(value => { state.status = 'succeeded'; state.value = value; }, error => { state.status = 'failed'; state.error = error; });
  return state;
};
const clock = t => t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: 0 });

test('message jobs post once and retain context through polls beyond the old 50 second deadline', async t => {
  clock(t);
  const requests = [];
  const service = new ApiClaimService({ fetchImpl: async (url, options) => {
    const request = new Request(`http://localhost${url}`, options);
    requests.push({ request, options, at: Date.now() });
    if (options.method === 'POST') return accepted();
    return Date.now() < 54000 ? pending() : succeeded();
  } });
  const result = observe(service.sendMessage(CASE, '合成問題', { document_id: 'application' }));
  await flush();
  assert.equal(result.status, 'pending');
  for (let index = 0; index < 17; index++) await advance(t, 3000);
  assert.equal(result.status, 'pending');
  await advance(t, 3000);
  assert.equal(result.status, 'succeeded');
  assert.deepEqual(result.value, answer());
  assert.equal(requests.filter(entry => entry.request.method === 'POST').length, 1);
  assert.equal(requests.length, 19);
  assert.equal(new URL(requests[0].request.url).pathname, '/api/v1/cases/synthetic%20case/message-jobs');
  assert.deepEqual(await requests[0].request.json(), { message: '合成問題', document_id: 'application' });
  assert.equal(requests[1].at, 3000);
  for (const { request, options } of requests) {
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.mode, 'same-origin');
    assert.equal(options.redirect, 'error');
    if (request.method === 'GET') assert.equal(new URL(request.url).pathname, `/api/v1/cases/synthetic%20case/message-jobs/${JOB}`);
  }
  await advance(t, 600000);
  assert.equal(requests.length, 19);
  assert.ok(requests.every(entry => !entry.options.signal.aborted));
});

test('pending jobs stop at the overall 330 second budget without posting another model request', async t => {
  clock(t);
  const methods = [];
  const service = new ApiClaimService({ fetchImpl: async (_url, options) => { methods.push(options.method); return options.method === 'POST' ? accepted() : pending(); } });
  const result = observe(service.sendMessage(CASE, '合成問題'));
  await flush();
  for (let index = 0; index < 109; index++) await advance(t, 3000);
  assert.equal(result.status, 'pending');
  await advance(t, 3000);
  assert.equal(result.status, 'failed');
  assert.equal(result.error.code, 'TIMEOUT');
  assert.equal(methods.filter(method => method === 'POST').length, 1);
  assert.equal(methods.filter(method => method === 'GET').length, 109);
  const count = methods.length;
  await advance(t, 600000);
  assert.equal(methods.length, count);
});

test('each job HTTP request is capped at 15 seconds and aborts without an automatic POST retry', async t => {
  clock(t);
  const requests = [];
  const service = new ApiClaimService({ timeout: 60000, fetchImpl: async (_url, options) => { requests.push(options); return new Promise(() => {}); } });
  const result = observe(service.sendMessage(CASE, '合成問題'));
  await flush();
  await advance(t, 14999);
  assert.equal(result.status, 'pending');
  await advance(t, 1);
  assert.equal(result.status, 'failed');
  assert.equal(result.error.code, 'TIMEOUT');
  assert.equal(requests[0].signal.aborted, true);
  await advance(t, 600000);
  assert.equal(requests.length, 1);
});

test('the overall deadline includes POST JSON parsing, polling sleep and a hung GET JSON body', async t => {
  clock(t);
  const requests = [];
  const service = new ApiClaimService({ messageTimeout: 6500, fetchImpl: async (_url, options) => {
    requests.push({ options, at: Date.now() });
    return options.method === 'POST'
      ? { ok: true, status: 202, json: () => new Promise(resolve => setTimeout(() => resolve({ id: JOB, status: 'pending' }), 2000)) }
      : { ok: true, status: 200, json: () => new Promise(() => {}) };
  } });
  const result = observe(service.sendMessage(CASE, '合成問題'));
  await flush();
  await advance(t, 2000);
  await advance(t, 3000);
  assert.equal(requests.length, 2);
  assert.equal(requests[1].at, 5000);
  await advance(t, 1499);
  assert.equal(result.status, 'pending');
  await advance(t, 1);
  assert.equal(result.error.code, 'TIMEOUT');
  assert.equal(requests[1].options.signal.aborted, true);
  await advance(t, 600000);
  assert.equal(requests.length, 2);
});

test('a polling sleep cannot exceed the remaining overall budget', async t => {
  clock(t);
  let calls = 0;
  const service = new ApiClaimService({ messageTimeout: 2500, fetchImpl: async () => { calls++; return accepted(); } });
  const result = observe(service.sendMessage(CASE, '合成問題'));
  await flush();
  await advance(t, 2499);
  assert.equal(result.status, 'pending');
  await advance(t, 1);
  assert.equal(result.error.code, 'TIMEOUT');
  await advance(t, 600000);
  assert.equal(calls, 1);
});

test('failed job envelopes preserve server error codes and HTTP statuses and stop polling', async t => {
  clock(t);
  for (const [code, status] of [['PROVIDER_UNAVAILABLE', 503], ['INVALID_AI_RESPONSE', 422], ['MESSAGE_JOB_CANCELLED', 409]]) {
    const requests = [];
    const service = new ApiClaimService({ fetchImpl: async (_url, options) => {
      requests.push(options);
      return options.method === 'POST' ? accepted() : Response.json({ id: JOB, status: 'failed', error: { code, message: '合成服務錯誤', status } });
    } });
    const result = observe(service.sendMessage(CASE, '合成問題'));
    await flush();
    await advance(t, 3000);
    assert.equal(result.status, 'failed');
    assert.equal(result.error.code, code);
    assert.equal(result.error.message, '合成服務錯誤');
    assert.equal(result.error.status, status);
    await advance(t, 600000);
    assert.equal(requests.length, 2);
    assert.ok(requests.every(options => !options.signal.aborted));
  }
});

test('creation requires HTTP 202, a UUID4 job id and a pending-only envelope before any poll', async t => {
  clock(t);
  for (const [body, status] of [
    [{ id: JOB, status: 'pending' }, 200],
    [{ id: JOB, status: 'succeeded', result: answer() }, 202],
    [{ id: 'https://unsafe.example/job', status: 'pending' }, 202],
    [{ id: '../job', status: 'pending' }, 202],
    [{ id: '12345678-1234-1234-8234-123456789abc', status: 'pending' }, 202],
    [{ id: JOB, status: 'pending', result: answer() }, 202],
    [null, 202],
  ]) {
    let calls = 0;
    const service = new ApiClaimService({ fetchImpl: async () => { calls++; return Response.json(body, { status }); } });
    const result = observe(service.sendMessage(CASE, '合成問題'));
    await flush();
    assert.equal(result.status, 'failed', JSON.stringify(body));
    assert.equal(result.error.code, 'INVALID_RESPONSE');
    await advance(t, 600000);
    assert.equal(calls, 1);
  }
});

test('poll results reject changed job ownership, unsafe ids and malformed terminal payloads', async t => {
  clock(t);
  for (const body of [
    { id: OTHER_JOB, status: 'pending' },
    { id: 'https://unsafe.example/job', status: 'pending' },
    { id: JOB, status: 'unknown' },
    { id: JOB, status: 'pending', result: answer() },
    { id: JOB, status: 'succeeded', result: answer('other-case') },
    { id: JOB, status: 'succeeded', result: { case: answer().case, response: null } },
    { id: JOB, status: 'succeeded', result: { case: answer().case, response: {} } },
    { id: JOB, status: 'succeeded', result: answer(), error: { code: 'WRONG', message: '合成', status: 500 } },
    { id: JOB, status: 'failed', error: { code: 'INVALID_AI_RESPONSE', message: '合成', status: '422' } },
    { id: JOB, status: 'failed', error: { code: 'INVALID_AI_RESPONSE', message: '合成', status: 200 } },
    { id: JOB, status: 'failed' },
  ]) {
    let calls = 0;
    const service = new ApiClaimService({ fetchImpl: async (_url, options) => { calls++; return options.method === 'POST' ? accepted() : Response.json(body); } });
    const result = observe(service.sendMessage(CASE, '合成問題'));
    await flush();
    await advance(t, 3000);
    assert.equal(result.status, 'failed', JSON.stringify(body));
    assert.equal(result.error.code, 'INVALID_RESPONSE');
    await advance(t, 600000);
    assert.equal(calls, 2);
  }
});

test('job creation validation, active-job conflicts and missing polls never fall back or repost', async t => {
  clock(t);
  for (const [at, code, status] of [['POST', 'VALIDATION_ERROR', 422], ['POST', 'MESSAGE_JOB_ACTIVE', 409], ['GET', 'MESSAGE_JOB_NOT_FOUND', 404]]) {
    const methods = [];
    const service = new ApiClaimService({ fetchImpl: async (_url, options) => {
      methods.push(options.method);
      return options.method === at ? Response.json({ error: { code, message: '合成錯誤' } }, { status }) : accepted();
    } });
    const result = observe(service.sendMessage(CASE, '合成問題'));
    await flush();
    if (at === 'GET') await advance(t, 3000);
    assert.equal(result.status, 'failed');
    assert.equal(result.error.code, code);
    assert.equal(result.error.status, status);
    await advance(t, 600000);
    assert.deepEqual(methods, at === 'POST' ? ['POST'] : ['POST', 'GET']);
  }
});

test('invalid case identifiers cannot normalize a job request onto a parent path', async () => {
  for (const id of [undefined, null, '', ' ', '.', '..', {}]) {
    let calls = 0;
    const service = new ApiClaimService({ fetchImpl: async () => { calls++; return accepted(); } });
    await assert.rejects(service.sendMessage(id, '合成問題'), error => error.code === 'VALIDATION_ERROR');
    assert.equal(calls, 0);
  }
});

test('a GET network failure is terminal without resubmitting the model request', async t => {
  clock(t);
  const methods = [];
  const service = new ApiClaimService({ fetchImpl: async (_url, options) => {
    methods.push(options.method);
    if (options.method === 'GET') throw new Error('synthetic offline');
    return accepted();
  } });
  const result = observe(service.sendMessage(CASE, '合成問題'));
  await flush();
  await advance(t, 3000);
  assert.equal(result.status, 'failed');
  assert.equal(result.error.code, 'NETWORK_ERROR');
  await advance(t, 600000);
  assert.deepEqual(methods, ['POST', 'GET']);
});
