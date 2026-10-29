import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { MockClaimService } from '../src/services/mock-claim-service.js';
import { routeRequest } from '../cloudflare/gateway.js';

// controlled_transport: 真瀏覽器及正式 adapter，回覆為合成 Mock 資料。
// 不連後端、模型或外部網站，也不保存含完整網址／標頭的 trace、HAR 或影片。
const syntheticKey = () => ['sk', 'or', 'v1', 'a'.repeat(64)].join('-');
const description = '我只有門診治療，沒有住院，也沒有手術。';
const missingKeyText = '展示金鑰尚未提供，請使用有效的展示連結。';

async function controlledTransport(page) {
  const fixture = new MockClaimService({ delay: 0, storage: null });
  const requests = [];
  const jobs = new Map();
  const state = { requests, unknown: 0, errors: 0, errorCategories: [], expected401Console: 0, deniedPosts: 0, redirectExpected: false, redirectConsole: 0, external: 0, refererLeaks: 0 };
  const origin = new URL(test.info().project.use.baseURL).origin;
  page.on('pageerror', () => { state.errors++; });
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const expected = /\/api\/v1\/cases\/[^/]+\/message-jobs$/.test(message.location().url)
      && /^Failed to load resource: the server responded with a status of 401\b/.test(message.text());
    const redirect = state.redirectExpected && /\/runtime-key-redirect-target$/.test(message.location().url)
      && /^Failed to load resource: net::ERR_FAILED$/.test(message.text());
    if (expected) state.expected401Console++;
    else if (redirect) state.redirectConsole++;
    else {
      state.errors++;
      const location = message.location().url ? new URL(message.location().url).pathname : '[no-location]';
      state.errorCategories.push(message.text().replaceAll(syntheticKey(), '[synthetic-key]').replace(/https?:\/\/\S+/g, '[url]').slice(0, 160) + ' @ ' + location);
    }
  });
  page.on('request', request => {
    if (request.headers().referer?.includes(syntheticKey())) state.refererLeaks++;
  });
  await page.context().route('**/*', async route => {
    if (new URL(route.request().url()).origin !== origin) {
      state.external++;
      return route.abort();
    }
    if (route.request().isNavigationRequest() && route.request().resourceType() === 'document') {
      // Exercise the production HTML with the actual edge security policy.
      // The asset fetch remains local; every API and external URL is intercepted.
      const response = await route.fetch();
      const edge = await routeRequest(new Request(route.request().url()), {
        assetFetch: async () => new Response(await response.body(), { status: response.status(), headers: response.headers() }),
      });
      return route.fulfill({ status: edge.status, headers: Object.fromEntries(edge.headers), body: Buffer.from(await edge.arrayBuffer()) });
    }
    return route.continue();
  });
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    if (new URL(request.url()).origin !== origin) {
      state.external++;
      return route.abort();
    }
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const header = request.headers()['x-openrouter-key'];
    const input = method === 'POST' || method === 'PATCH' ? request.postDataJSON() : null;
    requests.push({ path, method, hasKey: header !== undefined, keyMatches: header === syntheticKey(), bodyHasKey: JSON.stringify(input).includes(syntheticKey()) });
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body), headers: { 'Cache-Control': 'no-store' } });
    const casePath = path.match(/^\/api\/v1\/cases\/([^/]+)$/);
    const jobPath = path.match(/^\/api\/v1\/cases\/([^/]+)\/message-jobs$/);
    const pollPath = path.match(/^\/api\/v1\/cases\/([^/]+)\/message-jobs\/([^/]+)$/);
    if (path === '/api/v1/health') return json({ status: 'ok', service_mode: 'api', llm_provider: 'mock', llm_configured: header === syntheticKey(), llm_verified: false, ocr_provider: 'mock' });
    if (path === '/api/v1/claim-types') return json(await fixture.getClaimTypes());
    if (path === '/api/v1/sources/cardif-claims') return json(await fixture.getSource('cardif-claims'));
    if (path === '/api/v1/cases' && method === 'POST') return json(await fixture.createCase(input), 201);
    if (casePath && method === 'GET') return json(await fixture.getCase(casePath[1]));
    if (jobPath && method === 'POST') {
      if (!header) {
        state.deniedPosts++;
        return json({ error: { code: 'KEY_REQUIRED', message: missingKeyText } }, 401);
      }
      expect(header === syntheticKey(), '只接受本測試合成的標頭').toBe(true);
      expect(input).toEqual({ message: description });
      const id = randomUUID();
      jobs.set(id, { caseId: jobPath[1], result: await fixture.sendMessage(jobPath[1], input.message) });
      return json({ id, status: 'pending' }, 202);
    }
    if (pollPath && method === 'GET') {
      const job = jobs.get(pollPath[2]);
      expect(Boolean(job) && job.caseId === pollPath[1]).toBe(true);
      return json({ id: pollPath[2], status: 'succeeded', result: job.result });
    }
    state.unknown++;
    return json({ error: { code: 'CONTROLLED_UNEXPECTED_REQUEST', message: '受控驗收收到未預期的請求。' } }, 400);
  });
  return state;
}

async function assertPrivate(page) {
  const privacy = await page.evaluate(async key => {
    const contains = value => String(value).includes(key);
    const storageContains = storage => Array.from({ length: storage.length }, (_, i) => storage.key(i)).some(name => contains(name) || contains(storage.getItem(name)));
    const cacheNames = await caches.keys();
    let cacheContains = cacheNames.some(contains);
    for (const name of cacheNames) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        cacheContains ||= contains(request.url) || contains(JSON.stringify([...request.headers])) || contains(await response.text());
      }
    }
    return {
      session: storageContains(sessionStorage), local: storageContains(localStorage),
      dom: contains(document.documentElement.outerHTML), history: contains(JSON.stringify(history.state)),
      cookie: contains(document.cookie), cache: cacheContains,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  }, syntheticKey());
  expect(privacy).toEqual({ session: false, local: false, dom: false, history: false, cookie: false, cache: false, overflow: expect.any(Number) });
  expect(privacy.overflow).toBeLessThanOrEqual(1);
}

async function sendDescription(page) {
  await page.getByLabel('描述就醫情況', { exact: true }).fill(description);
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
}

function assertTransport(state) {
  expect(state.errorCategories, '不得有非預期 console 錯誤（分類已去除網址與合成金鑰）').toEqual([]);
  expect(state.errors, '不得有非預期 console 或 pageerror').toBe(0);
  expect(state.external, '不得外呼任何外部網站或模型').toBe(0);
  expect(state.unknown).toBe(0);
  expect(state.expected401Console, '只容許受控缺金鑰 POST 對應的瀏覽器 401 提示').toBe(state.deniedPosts);
  expect(state.refererLeaks, '同源子資源 Referer 不得包含合成金鑰').toBe(0);
  for (const request of state.requests) {
    expect(request.bodyHasKey).toBe(false);
    const necessary = request.method === 'GET' && request.path === '/api/v1/health'
      || request.method === 'POST' && request.path.endsWith('/message-jobs');
    if (!necessary) expect(request.hasKey).toBe(false);
  }
}

test('執行期連結清除網址、對話標頭限縮，重新整理後金鑰不會恢復', async ({ page }) => {
  const state = await controlledTransport(page);
  await page.goto('/?service=api&key=' + syntheticKey() + '&note=a%20b#assistant');
  await expect(page.getByLabel('描述就醫情況', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/\?service=api&note=a%20b#assistant$/);
  expect(state.requests.find(item => item.path === '/api/v1/health')?.keyMatches).toBe(true);
  await expect(page.locator('meta[name="referrer"]')).toHaveAttribute('content', 'no-referrer');
  await sendDescription(page);
  await expect.poll(() => state.requests.filter(item => item.path.includes('/message-jobs/') && item.method === 'GET').length).toBe(1);
  await expect(page.getByRole('button', { name: '送出描述', exact: true })).toBeEnabled();
  expect(state.requests.find(item => item.method === 'POST' && item.path.endsWith('/message-jobs'))?.keyMatches).toBe(true);
  await assertPrivate(page);

  const oldCount = state.requests.length;
  await page.reload();
  await expect(page.getByLabel('描述就醫情況', { exact: true })).toBeVisible();
  expect(state.requests.slice(oldCount).find(item => item.path === '/api/v1/health')?.hasKey).toBe(false);
  await sendDescription(page);
  await expect(page.getByRole('alert')).toContainText(missingKeyText);
  expect(state.requests.slice(oldCount).filter(item => item.path.endsWith('/message-jobs'))).toHaveLength(1);
  expect(state.requests.slice(oldCount).every(item => !item.hasKey)).toBe(true);
  await assertPrivate(page);
  assertTransport(state);
});

test('重複編碼參數清除後拒絕金鑰，錯誤保持 API 模式且不輪詢', async ({ page }) => {
  const state = await controlledTransport(page);
  await page.goto('/?key=' + syntheticKey() + '&service=api&%6bey=' + syntheticKey() + '&note=preserved#assistant');
  await expect(page.getByLabel('描述就醫情況', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/\?service=api&note=preserved#assistant$/);
  await sendDescription(page);
  await expect(page.getByRole('alert')).toContainText(missingKeyText);
  expect(state.requests.every(item => !item.hasKey)).toBe(true);
  expect(state.requests.filter(item => item.path.includes('/message-jobs/'))).toHaveLength(0);
  await assertPrivate(page);
  assertTransport(state);
});

test('Mock 連結也清除金鑰，完成模擬對話時沒有任何 API 或外部請求', async ({ page }) => {
  const state = await controlledTransport(page);
  await page.goto('/?service=mock&key=' + syntheticKey() + '&note=preserved#assistant');
  await expect(page.getByLabel('描述就醫情況', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/\?service=mock&note=preserved#assistant$/);
  await sendDescription(page);
  await expect(page.locator('#guided-thread .bubble')).not.toHaveCount(0);
  await expect(page.getByRole('button', { name: '送出描述', exact: true })).toBeEnabled();
  expect(state.requests).toHaveLength(0);
  await assertPrivate(page);
  assertTransport(state);
});

test('原生 fetch 拒絕 302，重新導向目標完全收不到請求或金鑰', async ({ page }) => {
  const state = await controlledTransport(page);
  state.redirectExpected = true;
  let originalHasKey = false;
  let targetRequests = 0;
  await page.route('**/runtime-key-redirect-target', route => {
    targetRequests++;
    return route.fulfill({ body: 'unexpected redirect target' });
  });
  await page.route('**/api/v1/health', route => {
    originalHasKey = route.request().headers()['x-openrouter-key'] === syntheticKey();
    return route.fulfill({ status: 302, headers: { Location: '/runtime-key-redirect-target', 'Cache-Control': 'no-store' }, body: '' });
  });
  const rejected = page.waitForEvent('requestfailed', request => new URL(request.url()).pathname === '/api/v1/health');
  await page.goto('/?service=api&key=' + syntheticKey() + '#assistant');
  expect((await rejected).failure()?.errorText).toBe('net::ERR_FAILED');
  await expect(page.getByRole('heading', { name: '服務暫時無法使用', exact: true })).toBeVisible();
  await expect(page.getByText('無法連線至服務，請確認網路後重試。', { exact: true })).toBeVisible();
  expect(originalHasKey).toBe(true);
  expect(targetRequests).toBe(0);
  await assertPrivate(page);
  assertTransport(state);
  expect(state.redirectConsole).toBe(1);
});
