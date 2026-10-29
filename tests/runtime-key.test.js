import test from 'node:test';
import assert from 'node:assert/strict';
import { consumeRuntimeKey } from '../src/runtime-key.js';

// Synthetic syntax only; no issued provider credential is used in this suite.
const syntheticKey = () => ['sk', 'or', 'v1', 'a'.repeat(64)].join('-');
const CASE = '12345678-1234-4234-8234-123456789abc';
const origin = 'https://claims.example';

function browserAt(suffix, { replaceError = false } = {}) {
  const location = new URL(origin + suffix);
  const history = {
    state: { existing: 'navigation state' },
    replacements: [],
    replaceState(state, title, path) {
      if (replaceError) throw new Error('synthetic history failure');
      this.replacements.push({ state, title, path });
      location.href = new URL(path, location.href).href;
    },
  };
  return { location, history };
}

test('有效網址金鑰立即移除，保留其他查詢、片段與既有 history state', () => {
  const browser = browserAt(`/demo?service=api&key=${syntheticKey()}&note=a%20b&flag#assistant`);
  const runtime = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(browser.location.href, origin + '/demo?service=api&note=a%20b&flag#assistant');
  assert.deepEqual(browser.history.replacements, [{
    state: { existing: 'navigation state' }, title: '', path: '/demo?service=api&note=a%20b&flag#assistant',
  }]);
  assert.equal(runtime.status, 'ready');
  assert.deepEqual(runtime.headersFor('/api/v1/health'), { 'X-OpenRouter-Key': syntheticKey() });
  assert.equal(JSON.stringify(runtime).includes(syntheticKey()), false);
  assert.equal(Object.isFrozen(runtime), true);
});

test('沒有網址金鑰不寫入 history，也不從上一個分頁實例復用金鑰', () => {
  const withKey = browserAt('/?key=' + syntheticKey());
  consumeRuntimeKey(withKey.location, withKey.history);
  const browser = browserAt('/?service=api#search');
  const runtime = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(runtime.status, 'absent');
  assert.deepEqual(runtime.headersFor('/api/v1/health'), {});
  assert.equal(browser.history.replacements.length, 0);
  assert.equal(browser.location.href, origin + '/?service=api#search');
});

test('移除前已清除的網址再次讀取不會復用先前 capability 的金鑰', () => {
  const browser = browserAt('/?key=' + syntheticKey());
  const first = consumeRuntimeKey(browser.location, browser.history);
  const second = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(first.status, 'ready');
  assert.equal(second.status, 'absent');
  assert.deepEqual(second.headersFor('/api/v1/health'), {});
});

test('拒絕重複 key，包括 percent encoded 參數名，並全部清除', () => {
  const browser = browserAt(`/?service=api&key=${syntheticKey()}&%6bey=${syntheticKey()}#workspace`);
  const runtime = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(runtime.status, 'rejected');
  assert.deepEqual(runtime.headersFor('/api/v1/health'), {});
  assert.equal(browser.location.href, origin + '/?service=api#workspace');
});

for (const [label, raw] of [
  ['空值', ''],
  ['缺少等號', null],
  ['未知格式', 'demo-only'],
  ['前置空白', '%20' + syntheticKey()],
  ['後置空白', syntheticKey() + '%20'],
  ['控制字元', syntheticKey() + '%0D%0AHeader%3Avalue'],
  ['尾端換行', syntheticKey() + '%0A'],
  ['錯誤 percent encoding', syntheticKey() + '%ZZ'],
  ['二次編碼', '%2573k-or-v1-' + 'a'.repeat(64)],
  ['長度不足', ['sk', 'or', 'v1', 'a'.repeat(63)].join('-')],
  ['長度過長', ['sk', 'or', 'v1', 'a'.repeat(65)].join('-')],
  ['非十六進位', ['sk', 'or', 'v1', 'z'.repeat(64)].join('-')],
]) test(`不合法金鑰安全拒絕且清除網址：${label}`, () => {
  const browser = browserAt('/?key' + (raw === null ? '' : '=' + raw) + '&service=api#assistant');
  const runtime = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(runtime.status, 'rejected');
  assert.deepEqual(runtime.headersFor('/api/v1/health'), {});
  assert.equal(browser.location.href, origin + '/?service=api#assistant');
});

test('percent encoded 金鑰只解碼一次，非 key 的參數保持原始編碼與順序', () => {
  const browser = browserAt('/?note=%2f%2F+%20&&%6Bey=%73k-or-v1-' + 'a'.repeat(64) + '&x=1&x=2#summary');
  const runtime = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(runtime.status, 'ready');
  assert.equal(browser.location.href, origin + '/?note=%2f%2F+%20&&x=1&x=2#summary');
});

test('無法清除網址時拒絕使用金鑰，也不外洩底層例外或網址', () => {
  const browser = browserAt('/?key=' + syntheticKey(), { replaceError: true });
  const runtime = consumeRuntimeKey(browser.location, browser.history);

  assert.equal(runtime.status, 'rejected');
  assert.deepEqual(runtime.headersFor('/api/v1/health'), {});
  assert.equal(JSON.stringify(runtime).includes(syntheticKey()), false);
});

test('只有同源 health 與建立對話端點取得標頭，輪詢、OCR 及一般 API 不帶金鑰', () => {
  const browser = browserAt('/?key=' + syntheticKey());
  const runtime = consumeRuntimeKey(browser.location, browser.history);
  const allowed = [
    ['/api/v1/health', 'GET'],
    [`/api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [`/api/v1/cases/${CASE}/messages`, 'POST'],
    [`${origin}/api/v1/cases/${CASE}/message-jobs`, 'post'],
  ];
  for (const [url, method] of allowed) assert.deepEqual(runtime.headersFor(url, method), { 'X-OpenRouter-Key': syntheticKey() });
  const denied = [
    ['/api/v1/health', 'POST'],
    ['/api/v1/claim-types', 'GET'],
    ['/api/v1/cases', 'POST'],
    [`/api/v1/cases/${CASE}/message-jobs`, 'GET'],
    [`/api/v1/cases/${CASE}/message-jobs/${CASE}`, 'GET'],
    [`/api/v1/cases/${CASE}/documents/application/analyze`, 'POST'],
    [`https://external.example/api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [`//external.example/api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [`https://claims.example@external.example/api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [`http://claims.example/api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [`${origin}:444/api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [`/api/v1/cases/${CASE}/message-jobs?next=other`, 'POST'],
    [`/api/v1/cases/${CASE}/message-jobs#other`, 'POST'],
    ['/api/v1/cases/../message-jobs', 'POST'],
    ['/api/v1/cases/%2f%2fexternal.example/message-jobs', 'POST'],
    ['/api/v1/cases/invalid/message-jobs', 'POST'],
    [`/api/v1/cases/${CASE}/message-jobs/`, 'POST'],
    [`\\external.example\api\v1\cases\${CASE}\message-jobs`, 'POST'],
    [` /api/v1/cases/${CASE}/message-jobs`, 'POST'],
    [null, 'POST'],
    [`/api/v1/cases/${CASE}/message-jobs`, null],
  ];
  for (const [url, method] of denied) assert.deepEqual(runtime.headersFor(url, method), {}, String(url));
});

test('每次標頭為獨立物件，不能藉修改回傳物件影響後續請求', () => {
  const browser = browserAt('/?key=' + syntheticKey());
  const runtime = consumeRuntimeKey(browser.location, browser.history);
  const first = runtime.headersFor('/api/v1/health');
  first['X-OpenRouter-Key'] = 'modified';

  assert.deepEqual(runtime.headersFor('/api/v1/health'), { 'X-OpenRouter-Key': syntheticKey() });
});
