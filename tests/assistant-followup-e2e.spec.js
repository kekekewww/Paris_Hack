import { test, expect } from '@playwright/test';

if (!process.env.CLAIM_API_BASE_URL) {
  throw new Error('連續引導驗收需要 CLAIM_API_BASE_URL。');
}
const originHeaders = { Origin: new URL(process.env.CLAIM_API_BASE_URL).origin };
const endpoint = (response, suffix, method = 'POST') =>
  new URL(response.url()).pathname.endsWith(suffix) && response.request().method() === method;
const activeId = (page, mode) => page.evaluate((serviceMode) =>
  sessionStorage.getItem(`cardif-active-${serviceMode}-v1`), mode);
const assistantBubbles = (page) => page.locator('#guided-thread .bubble:not(.user)');

async function assertLayout(page) {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, '連續引導與工作區不可橫向溢出').toBeLessThanOrEqual(1);
}

async function readCase(page, mode, id) {
  expect(typeof id, '操作後必須有案件 ID').toBe('string');
  page.__followupCaseIds.add(id);
  if (mode === 'api') {
    const response = await page.request.get(`/api/v1/cases/${id}`);
    expect(response.status()).toBe(200);
    return response.json();
  }
  const item = await page.evaluate((caseId) =>
    JSON.parse(sessionStorage.getItem('cardif-claim-demo-cases-v1') || '{}')[caseId] || null, id);
  expect(Boolean(item), 'Mock 案件必須確實保存於服務儲存區').toBe(true);
  return item;
}

async function currentCase(page, mode) {
  return readCase(page, mode, await activeId(page, mode));
}

function assertProvider(response, mode) {
  expect(response.provider).toBe(mode === 'mock' ? 'mock' : 'grounded_rules');
  expect(response.is_simulated).toBe(mode === 'mock');
}

async function sendDescription(page, mode, text, turn) {
  const answered = mode === 'api' ? page.waitForResponse((response) =>
    /^\/api\/v1\/cases\/[^/]+\/messages$/.test(new URL(response.url()).pathname)
    && response.request().method() === 'POST') : null;
  await page.getByLabel('描述就醫情況', { exact: true }).fill(text);
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  let actual;
  if (answered) {
    const response = await answered;
    expect(response.status()).toBe(200);
    actual = (await response.json()).response;
    assertProvider(actual, mode);
  }
  await expect(assistantBubbles(page)).toHaveCount(turn);
  await expect(page.getByRole('button', { name: '送出描述', exact: true })).toBeEnabled();
  const item = await currentCase(page, mode);
  const responses = item.messages.filter((entry) => entry.role === 'assistant');
  expect(responses.length).toBe(turn);
  actual ||= responses.at(-1).response;
  assertProvider(actual, mode);
  expect(actual.message === responses.at(-1).content, '畫面與保存的回覆必須來自相同服務結果').toBe(true);
  const body = assistantBubbles(page).last().locator(':scope > div').nth(1);
  await expect.poll(async () => (await body.textContent()) === actual.message,
    { message: '最新對話本文必須顯示本輪回覆，不以舊訊息滿足斷言' }).toBe(true);
  await assertLayout(page);
  return { item, response: actual };
}

async function assertUnbuilt(page, item) {
  expect(item.claim_type_id).toBeNull();
  expect(item.documents.length).toBe(0);
  expect(page.__followupPatchCount, '引導與選型不可先發送案件 PATCH').toBe(0);
  await expect(page).toHaveURL(/#assistant$/);
}

async function assertMessageLabels(page, mode, count) {
  const labels = assistantBubbles(page).locator('.speaker .message-provider');
  await expect(labels).toHaveCount(count);
  for (let index = 0; index < count; index += 1) {
    await expect(labels.nth(index)).toHaveText(mode === 'mock' ? '模擬' : '規則引導');
  }
}

async function buildGuided(page, mode, label, claimTypeId) {
  const picker = page.locator('fieldset.guided-type-picker');
  await expect(picker).toBeVisible();
  await expect(picker.locator('input[name="guided-claim-type"]:checked')).toHaveCount(0);
  const build = page.getByRole('button', { name: '建立文件清單', exact: true });
  await expect(build).toBeDisabled();
  const beforeChoice = await currentCase(page, mode);
  await assertUnbuilt(page, beforeChoice);
  const radio = picker.getByRole('radio', { name: label, exact: true });
  await radio.check();
  await expect(radio).toBeChecked();
  await expect(build).toBeEnabled();
  expect(JSON.stringify(await currentCase(page, mode)) === JSON.stringify(beforeChoice), '點選 radio 只能更新草稿，不可先改案').toBe(true);
  expect(page.__followupPatchCount).toBe(0);
  const built = mode === 'api'
    ? page.waitForResponse((response) => endpoint(response, `/cases/${beforeChoice.id}`, 'PATCH'))
    : null;
  await build.click();
  if (built) {
    const response = await built;
    expect(response.status()).toBe(200);
    expect(response.request().postDataJSON().claim_type_id).toBe(claimTypeId);
  }
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  const item = await currentCase(page, mode);
  expect(item.id).toBe(beforeChoice.id);
  expect(item.claim_type_id).toBe(claimTypeId);
  expect(item.documents.length).toBeGreaterThan(0);
  expect(page.__followupPatchCount).toBe(mode === 'api' ? 1 : 0);
  await assertLayout(page);
  return item;
}

async function returnHome(page) {
  await page.locator('#app .header-nav').getByRole('button', { name: '返回首頁', exact: true }).click();
  await expect(page).toHaveURL(/#triage$/);
}

for (const mode of ['mock', 'api']) {
  test.describe(mode, () => {
    test.beforeEach(async ({ page }) => {
      page.__followupCaseIds = new Set();
      page.__followupCreatedReads = [];
      page.__followupPatchCount = 0;
      page.__followupCreateCount = 0;
      page.__followupMessageCount = 0;
      page.__followupErrors = 0;
      page.on('pageerror', () => { page.__followupErrors += 1; });
      page.on('console', (message) => {
        if (message.type() === 'error') page.__followupErrors += 1;
      });
      page.on('request', (request) => {
        const path = new URL(request.url()).pathname;
        if (/^\/api\/v1\/cases\/[^/]+$/.test(path) && request.method() === 'PATCH') page.__followupPatchCount += 1;
        if (path === '/api/v1/cases' && request.method() === 'POST') page.__followupCreateCount += 1;
        if (/^\/api\/v1\/cases\/[^/]+\/messages$/.test(path) && request.method() === 'POST') page.__followupMessageCount += 1;
      });
      page.on('response', (response) => {
        if (endpoint(response, '/api/v1/cases') && response.status() === 201) {
          // 即使送出訊息途中失敗，也能清除剛由 UI 建立的合成案件。
          page.__followupCreatedReads.push(response.json().then((item) => {
            if (typeof item.id === 'string') page.__followupCaseIds.add(item.id);
          }));
        }
      });
    });

    test.afterEach(async ({ page }) => {
      await Promise.allSettled(page.__followupCreatedReads);
      if (mode === 'api') {
        for (const id of page.__followupCaseIds) {
          const deleted = await page.request.delete(`/api/v1/cases/${id}`, { headers: originHeaders });
          expect([200, 404].includes(deleted.status()), '測試結束必須清除所有測試案件').toBe(true);
          expect((await page.request.get(`/api/v1/cases/${id}`)).status()).toBe(404);
        }
      } else {
        // 隔離 browser context 的測試資料清理，不作為產品行為通過的證據。
        await page.evaluate(() => {
          sessionStorage.removeItem('cardif-claim-demo-cases-v1');
          sessionStorage.removeItem('cardif-active-mock-v1');
        });
      }
      expect(page.__followupErrors, '不得出現未處理例外或 console 錯誤；不記錄原始訊息').toBe(0);
    });

    test('逐輪釐清就醫資訊，確認門診後才提供可獨立建立的候選', async ({ page }, testInfo) => {
      await page.goto(`/?service=${mode}#triage`);
      await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
      const turns = [];
      for (const [index, text] of ['你好', '我出車禍了', '沒有住院'].entries()) {
        const result = await sendDescription(page, mode, text, index + 1);
        turns.push(result);
        expect(result.response.response_type).toBe('clarification');
        expect(result.response.suggested_claim_types.length).toBe(0);
        expect(Object.keys(result.response.proposed_case_updates).length).toBe(0);
        await assertUnbuilt(page, result.item);
        await expect(page.locator('fieldset.guided-type-picker')).toHaveCount(0);
      }
      const third = turns[2].response.message;
      expect(/門診|急診/.test(third), '確認沒有住院後應釐清門診、急診或尚未就醫').toBe(true);
      expect(/(?:是否|有沒有|有無|是不是).{0,6}住院|(?:已住院|是住院)[、，,]\s*只有門診|確診癌症/.test(third), '第三輪可承認沒有住院，不可重問住院或確診癌症').toBe(false);
      expect(new Set(turns.map((turn) => turn.response.message)).size, '每輪追問必須依已知資訊前進，不可反覆給相同問題').toBe(3);
      expect(turns.every((turn) => turn.item.id === turns[0].item.id), '同一次引導必須沿用同一未分類案件').toBe(true);
      // 放在語意斷言後，舊版 RED 首先指出真正的重複追問缺陷。
      await assertMessageLabels(page, mode, 3);
      if (process.env.FOLLOWUP_SCREENSHOTS === '1' && mode === 'api') {
        // 僅明確要求時保存三個尺寸各一張；畫面只有本測試的三句合成描述。
        await page.evaluate(async () => {
          const finite = document.getAnimations().filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity);
          await Promise.all(finite.map((animation) => animation.finished.catch(() => {})));
          window.scrollTo(0, 0);
        });
        await page.screenshot({ path: testInfo.outputPath('guided-third-turn.png'), fullPage: true });
      }

      const fourth = await sendDescription(page, mode, '只有去門診，沒有手術', 4);
      expect(fourth.response.response_type).toBe('claim_suggestion');
      expect(fourth.response.suggested_claim_types.map((type) => type.id)).toEqual(['outpatient']);
      expect(fourth.response.proposed_case_updates.claim_type_id).toBe('outpatient');
      await assertUnbuilt(page, fourth.item);
      await assertMessageLabels(page, mode, 4);
      const built = await buildGuided(page, mode, '醫療門診', 'outpatient');
      expect(built.conditions.cause).toBe('accident');
      expect(built.conditions.surgery).toBe('no');
      expect(page.__followupCreateCount).toBe(mode === 'api' ? 1 : 0);
      expect(page.__followupMessageCount).toBe(mode === 'api' ? 4 : 0);
    });

    test('已建立的引導案件回首頁再描述，先清空 intake 畫面並保留原工作區', async ({ page }) => {
      await page.goto(`/?service=${mode}#triage`);
      await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
      const first = await sendDescription(page, mode, '我因車禍住院三天，沒有手術。', 1);
      expect(first.response.response_type).toBe('claim_suggestion');
      const original = await buildGuided(page, mode, '住院醫療', 'inpatient');
      const snapshot = JSON.stringify(original);
      const creationCount = page.__followupCreateCount;
      await returnHome(page);
      await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
      await expect(page).toHaveURL(/#assistant$/);
      await expect(page.getByRole('log', { name: '引導對話', exact: true }).locator('.bubble')).toHaveCount(0);
      await expect(page.getByLabel('描述就醫情況', { exact: true })).toHaveValue('');
      await expect(page.locator('fieldset.guided-type-picker')).toHaveCount(0);
      expect(await activeId(page, mode)).toBe(original.id);
      expect(page.__followupCreateCount, '開啟新的描述畫面不可先建立或切換案件').toBe(creationCount);
      expect(JSON.stringify(await readCase(page, mode, original.id)) === snapshot, '開啟新描述不得覆寫原案件').toBe(true);
      await assertLayout(page);

      await page.locator('#app .header-nav').getByRole('button', { name: '繼續準備', exact: true }).click();
      await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
      expect(await activeId(page, mode)).toBe(original.id);
      expect(JSON.stringify(await currentCase(page, mode)) === snapshot, '未送新描述時仍可回原工作區繼續準備').toBe(true);
      await expect(page.locator('article[data-document-id]')).toHaveCount(original.documents.length);

      await returnHome(page);
      await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
      await expect(assistantBubbles(page)).toHaveCount(0);
      await page.getByLabel('描述就醫情況', { exact: true }).fill('你好');
      expect(await activeId(page, mode)).toBe(original.id);
      expect(page.__followupCreateCount).toBe(creationCount);
      const fresh = await sendDescription(page, mode, '你好', 1);
      expect(fresh.item.id !== original.id, '真正送出新描述後才建立不同案件').toBe(true);
      expect(fresh.item.claim_type_id).toBeNull();
      expect(fresh.item.documents.length).toBe(0);
      expect(fresh.item.messages.length).toBe(2);
      expect(fresh.item.messages.filter((message) => message.role === 'user').every((message) => message.content === '你好')).toBe(true);
      expect(fresh.response.response_type).toBe('clarification');
      expect(JSON.stringify(await readCase(page, mode, original.id)) === snapshot, '新引導送出後原案件仍完整保存').toBe(true);
      expect(page.__followupPatchCount).toBe(mode === 'api' ? 1 : 0);
      expect(page.__followupCreateCount).toBe(mode === 'api' ? 2 : 0);
      expect(page.__followupMessageCount).toBe(mode === 'api' ? 2 : 0);
      await assertMessageLabels(page, mode, 1);
      await assertLayout(page);
    });
  });
}
