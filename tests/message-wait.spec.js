import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { MockClaimService } from '../src/services/mock-claim-service.js';

// controlled_transport：只驗真瀏覽器 API adapter / UI；不是後端、OpenRouter 或費用驗證。
// Fixture 原樣保留 provider=mock / is_simulated=true，避免將合成結果冒充真正模型回覆。
const syntheticDescription = '我因車禍只有門診，沒有住院，也沒有手術。';
const failureText = '受控傳輸合成錯誤：本次工作失敗，請手動重試。';
// 只在回歸 RED 驗證時，把最後提交的舊 adapter 作為瀏覽器基準；不修改產品檔案。
const baselineAdapter = process.env.MESSAGE_WAIT_BASELINE === '1'
  ? execFileSync('git', ['-c', 'safe.directory=D:/Developing/Paris', 'show', 'HEAD:src/services/api-claim-service.js'], { encoding: 'utf8' })
  : null;

async function controlledTransport(page) {
  if (baselineAdapter) {
    expect(baselineAdapter.includes('message-jobs'), 'RED 基準必須確實是尚未實作 job 的已提交 adapter').toBe(false);
    await page.route('**/src/services/api-claim-service.js*', (route) => route.fulfill({
      contentType: 'application/javascript', body: baselineAdapter,
    }));
  }
  const service = new MockClaimService({ delay: 0, storage: null });
  const state = {
    service,
    cases: new Set(),
    jobs: new Map(),
    posts: 0,
    gets: 0,
    patches: 0,
    legacyPosts: 0,
    unknown: 0,
    inFlight: 0,
    maxInFlight: 0,
    networkFailures: 0,
    completedGets: 0,
    nextTerminal: 'succeeded',
    terminalAllowed: false,
  };
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;
    const casePath = path.match(/^\/api\/v1\/cases\/([^/]+)$/);
    const startPath = path.match(/^\/api\/v1\/cases\/([^/]+)\/message-jobs$/);
    const pollPath = path.match(/^\/api\/v1\/cases\/([^/]+)\/message-jobs\/([^/]+)$/);
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    state.inFlight += 1;
    state.maxInFlight = Math.max(state.maxInFlight, state.inFlight);
    try {
      if (path === '/api/v1/health' && method === 'GET') return await json({
        status: 'ok', service_mode: 'api', llm_provider: 'mock', llm_configured: false, llm_verified: false, ocr_provider: 'mock',
      });
      if (path === '/api/v1/claim-types' && method === 'GET') return await json(await service.getClaimTypes());
      if (path === '/api/v1/sources/cardif-claims' && method === 'GET') return await json(await service.getSource('cardif-claims'));
      if (path === '/api/v1/cases' && method === 'POST') {
        const item = await service.createCase(request.postDataJSON());
        state.cases.add(item.id);
        return await json(item, 201);
      }
      if (casePath && method === 'GET') return await json(await service.getCase(casePath[1]));
      if (casePath && method === 'PATCH') {
        state.patches += 1;
        return await json(await service.updateCase(casePath[1], request.postDataJSON()));
      }
      if (casePath && method === 'DELETE') {
        state.cases.delete(casePath[1]);
        return await json(await service.deleteCase(casePath[1]));
      }
      if (startPath && method === 'POST') {
        state.posts += 1;
        const id = randomUUID();
        const input = request.postDataJSON();
        expect(input).toEqual({ message: syntheticDescription });
        state.jobs.set(id, { id, caseId: startPath[1], input, terminal: state.nextTerminal, result: null });
        return await json({ id, status: 'pending' }, 202);
      }
      if (pollPath && method === 'GET') {
        state.gets += 1;
        const job = state.jobs.get(pollPath[2]);
        expect(Boolean(job) && job.caseId === pollPath[1], '輪詢必須沿用同一案件和建立時的工作 ID').toBe(true);
        if (!state.terminalAllowed) return await json({ id: job.id, status: 'pending' });
        state.completedGets += 1;
        if (job.terminal === 'failed') return await json({
          id: job.id, status: 'failed', error: { code: 'PROVIDER_UNAVAILABLE', message: failureText, status: 503 },
        });
        job.result ||= await service.sendMessage(job.caseId, job.input.message);
        return await json({ id: job.id, status: 'succeeded', result: job.result });
      }
      if (/\/messages$/.test(path) && method === 'POST') state.legacyPosts += 1;
      else state.unknown += 1;
      return await json({ error: { code: 'CONTROLLED_UNEXPECTED_REQUEST', message: '受控驗收收到未預期的 API 路徑。' } }, 400);
    } finally {
      state.inFlight -= 1;
    }
  });
  page.on('requestfailed', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/v1/')) state.networkFailures += 1;
  });
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const banner = document.createElement('div');
      banner.textContent = 'controlled_transport｜受控合成資料，未呼叫模型或後端';
      banner.style.cssText = 'padding:8px;background:#fff3cd;color:#4b3b00;text-align:center;font:12px sans-serif;overflow-wrap:anywhere';
      document.body.prepend(banner);
    });
  });
  return state;
}

async function assertLayout(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, '長等待提示在桌面及手機不可橫向溢出').toBeLessThanOrEqual(1);
}

async function begin(page) {
  await page.clock.install({ time: new Date('2026-10-20T00:00:00Z') });
  await page.goto('/?service=api#triage');
  await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
  await page.getByLabel('描述就醫情況', { exact: true }).fill(syntheticDescription);
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
}

async function assertWaiting(page, state, posts = 1) {
  await expect.poll(() => state.posts, { message: '對話必須以單次短 POST 建立非同步工作' }).toBe(posts);
  await expect(page.locator('#busy-status')).toContainText(/最多等候\s*5\s*分鐘/);
  await expect(page.getByRole('button', { name: '送出描述', exact: true })).toBeDisabled();
  await expect(page.locator('input[name="guided-claim-type"]:enabled')).toHaveCount(0);
  await expect(page.locator('button[data-action="build-guided-checklist"]:enabled')).toHaveCount(0);
  expect(state.patches).toBe(0);
  expect(state.legacyPosts, '不得退回舊同步 messages 請求').toBe(0);
  await assertLayout(page);
}

async function advancePoll(page, state, milliseconds = 3000) {
  const previous = state.gets;
  await page.clock.runFor(milliseconds);
  await expect.poll(() => state.gets, { message: '虛擬時間推進後必須以短 GET 輪詢原工作' }).toBeGreaterThan(previous);
  await expect.poll(() => state.inFlight, { message: 'pending GET 必須迅速結束，不能形成長 HTTP 連線' }).toBe(0);
}

async function assertUnbuilt(page, state) {
  const id = await page.evaluate(() => sessionStorage.getItem('cardif-active-api-v1'));
  const item = await state.service.getCase(id);
  expect(item.claim_type_id).toBeNull();
  expect(item.documents.length).toBe(0);
  expect(state.patches).toBe(0);
  return item;
}

test.beforeEach(async ({ page }) => {
  page.__messageWaitErrors = 0;
  page.on('pageerror', () => { page.__messageWaitErrors += 1; });
  page.on('console', (message) => {
    if (message.type() === 'error') page.__messageWaitErrors += 1;
  });
});

test.afterEach(async ({ page }) => {
  const state = page.__messageWaitState;
  if (state) {
    for (const id of [...state.cases]) {
      // APIRequestContext 不經 page.route；只清除 fixture 儲存區，不發送真後端請求。
      await state.service.deleteCase(id);
      state.cases.delete(id);
    }
    expect(state.unknown).toBe(0);
    expect(state.networkFailures).toBe(0);
  }
  expect(page.__messageWaitErrors, '受控等待流程不得有 console 或 pageerror；不保存原始錯誤文字').toBe(0);
});

test('controlled_transport：跨125秒仍單次建立與短輪詢，成功後才容許確認清單', async ({ page }, testInfo) => {
  const state = await controlledTransport(page);
  page.__messageWaitState = state;
  await begin(page);
  await assertWaiting(page, state);
  const startTime = await page.evaluate(() => Date.now());
  for (let index = 0; index < 42; index += 1) await advancePoll(page, state);
  expect(await page.evaluate(() => Date.now()) - startTime).toBeGreaterThanOrEqual(126_000);
  await assertWaiting(page, state);
  expect(state.gets).toBeGreaterThanOrEqual(42);
  expect(state.maxInFlight).toBe(1);
  await assertUnbuilt(page, state);
  await page.evaluate(async () => {
    const finite = document.getAnimations().filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity);
    await Promise.all(finite.map((animation) => animation.finished.catch(() => {})));
    window.scrollTo(0, 0);
  });
  await page.screenshot({ path: testInfo.outputPath('controlled-wait-beyond-125s.png'), fullPage: true });

  state.terminalAllowed = true;
  await advancePoll(page, state);
  const picker = page.locator('fieldset.guided-type-picker');
  await expect(picker).toBeVisible();
  await expect(page.getByRole('button', { name: '送出描述', exact: true })).toBeEnabled();
  await expect(page.locator('#busy-status')).toHaveText('');
  await expect(page.locator('#guided-thread .message-provider')).toHaveText('模擬');
  await expect(picker.locator('input:checked')).toHaveCount(0);
  const before = await assertUnbuilt(page, state);
  await picker.getByRole('radio', { name: '醫療門診', exact: true }).check();
  expect(state.patches).toBe(0);
  expect(JSON.stringify(await state.service.getCase(before.id)) === JSON.stringify(before)).toBe(true);
  await page.getByRole('button', { name: '建立文件清單', exact: true }).click();
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  expect(state.patches).toBe(1);
  expect((await state.service.getCase(before.id)).claim_type_id).toBe('outpatient');
  const polls = state.gets;
  await page.clock.runFor(30_000);
  expect(state.posts).toBe(1);
  expect(state.gets).toBe(polls);
  await assertLayout(page);
});

test('controlled_transport：終態錯誤不自動重送，只有使用者重試才建立下一次工作', async ({ page }) => {
  const state = await controlledTransport(page);
  page.__messageWaitState = state;
  state.nextTerminal = 'failed';
  await begin(page);
  await assertWaiting(page, state);
  state.terminalAllowed = true;
  await advancePoll(page, state);
  await expect(page.getByRole('alert')).toContainText(failureText);
  await expect(page.getByRole('button', { name: '送出描述', exact: true })).toBeEnabled();
  await expect(page.locator('#busy-status')).toHaveText('');
  await assertUnbuilt(page, state);
  const polls = state.gets;
  await page.clock.runFor(126_000);
  expect(state.posts).toBe(1);
  expect(state.gets).toBe(polls);

  state.nextTerminal = 'succeeded';
  state.terminalAllowed = false;
  await page.getByRole('button', { name: '重試', exact: true }).click();
  await assertWaiting(page, state, 2);
  state.terminalAllowed = true;
  await advancePoll(page, state);
  await expect(page.locator('fieldset.guided-type-picker')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await assertUnbuilt(page, state);
  const id = await page.evaluate(() => sessionStorage.getItem('cardif-active-api-v1'));
  expect((await state.service.getCase(id)).messages.length).toBe(2);
  expect(state.jobs.size).toBe(2);
  expect(state.posts).toBe(2);
  await assertLayout(page);
});
