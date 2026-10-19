import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

// 即使以其他 config 指定此檔，也不能省略明確的真實請求授權旗標。
if (process.env.LIVE_OPENROUTER !== '1' || !process.env.CLAIM_API_BASE_URL) {
  throw new Error('此測試需要 LIVE_OPENROUTER=1 與 CLAIM_API_BASE_URL。');
}
const apiOrigin = new URL(process.env.CLAIM_API_BASE_URL).origin;
const originHeaders = { Origin: apiOrigin };
const registry = JSON.parse(await readFile(resolve('data/official-sources.json'), 'utf8'));
const sources = new Map(registry.sources.map((source) => [source.source_id, source]));
const surgeryDocument = registry.documents.find((document) => document.document_id === 'surgery');
const surgeryEvidence = [
  ...registry.knowledge.filter((entry) => entry.knowledge_id === 'surgery-condition'),
  ...registry.rules.filter((rule) => rule.claim_type_id === 'inpatient' && rule.document_id === 'surgery')
    .map((rule) => ({ ...rule, text: `${surgeryDocument.description} ${rule.explanation}` })),
];
const evidenceQuestion = '手術證明是否需要另附？';
const injectedFailureMessage = '驗收用單次對話服務中斷，請重試。';
const endpoint = (response, suffix, method = 'POST') =>
  new URL(response.url()).pathname.endsWith(suffix) && response.request().method() === method;
const preparationSnapshot = (item) => JSON.stringify({
  claim_type_id: item.claim_type_id,
  conditions: item.conditions,
  documents: item.documents,
});

function assertSources(references, { allowEmpty = false } = {}) {
  expect(Array.isArray(references), '官方引用必須是陣列').toBe(true);
  if (!allowEmpty) expect(references.length, '回答必須附上官方引用').toBeGreaterThan(0);
  const seen = new Set();
  for (const reference of references) {
    const canonical = sources.get(reference.source_id);
    expect(Boolean(canonical), '引用的來源 ID 必須存在於官方來源登錄').toBe(true);
    expect(reference.verification_status).toBe('verified');
    expect(reference.official_url === canonical.official_url, '引用網址必須與已查核來源完全一致').toBe(true);
    const url = new URL(reference.official_url);
    expect(url.protocol).toBe('https:');
    expect(url.hostname).toBe('life.cardif.com.tw');
    expect(url.username === '' && url.password === '' && url.hash === '', '官方引用不得夾帶帳密或片段').toBe(true);
    expect(url.port === '' || url.port === '443').toBe(true);
    if (reference.page_number !== null) {
      expect(Number.isInteger(reference.page_number)).toBe(true);
      expect(reference.page_number).toBeGreaterThanOrEqual(1);
      expect(reference.page_number).toBeLessThanOrEqual(canonical.page_count);
    }
    const key = `${reference.source_id}:${reference.page_number}`;
    expect(seen.has(key), '同一來源頁碼不可重複').toBe(false);
    seen.add(key);
  }
}

async function getCase(page, id) {
  const response = await page.request.get(`/api/v1/cases/${id}`);
  expect(response.status()).toBe(200);
  return response.json();
}

async function assertLayout(page) {
  const overflow = await page.evaluate(() => {
    const dialog = document.querySelector('dialog[open]');
    return {
      page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      dialog: dialog ? dialog.scrollWidth - dialog.clientWidth : 0,
    };
  });
  expect(overflow.page, '頁面不可橫向溢出').toBeLessThanOrEqual(1);
  expect(overflow.dialog, '文件檢查視窗不可橫向溢出').toBeLessThanOrEqual(1);
}

async function assertHealth(page, { verified = false } = {}) {
  const response = await page.request.get('/api/v1/health');
  expect(response.status()).toBe(200);
  const health = await response.json();
  expect(health.status).toBe('ok');
  expect(health.service_mode).toBe('api');
  expect(health.llm_provider).toBe('openai_compatible');
  expect(health.llm_configured).toBe(true);
  expect(typeof health.llm_verified).toBe('boolean');
  if (verified) expect(health.llm_verified, '同一後端程序必須記錄成功的真實模型驗證').toBe(true);
}

async function assertRenderedPDF(dialog) {
  const canvas = dialog.locator('canvas').first();
  await expect(canvas).toBeVisible();
  await expect.poll(() => canvas.evaluate((element) => {
    if (element.width < 100 || element.height < 100) return false;
    const pixels = element.getContext('2d').getImageData(0, 0, element.width, element.height).data;
    const stride = Math.max(1, Math.floor(pixels.length / 4 / 20_000));
    let ink = 0;
    for (let index = 0; index < pixels.length; index += stride * 4) {
      if (pixels[index + 3] > 0 && Math.min(pixels[index], pixels[index + 1], pixels[index + 2]) < 220) ink += 1;
    }
    return ink > 5;
  }), { message: 'PDF 預覽必須實際繪製合成文件，不能只有空白畫布' }).toBe(true);
}

test.beforeEach(async ({ page }) => {
  page.__liveCaseIds = new Set();
  page.__liveUnexpectedErrors = 0;
  page.__liveExpected503URL = null;
  page.__liveExpected503Count = 0;
  page.on('pageerror', () => { page.__liveUnexpectedErrors += 1; });
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    // 只容許精確案件 URL 的單次刻意注入失敗，其他 503 仍是測試錯誤。
    if (message.location().url === page.__liveExpected503URL
        && /^Failed to load resource: the server responded with a status of 503\b/.test(message.text())
        && page.__liveExpected503Count === 0) {
      page.__liveExpected503Count += 1;
      return;
    }
    // 不保存原始 console/例外文字，避免失敗輸出夾帶對話或 session 資料。
    page.__liveUnexpectedErrors += 1;
  });
});

test.afterEach(async ({ page }) => {
  for (const id of page.__liveCaseIds) {
    const deleted = await page.request.delete(`/api/v1/cases/${id}`, { headers: originHeaders });
    expect([200, 404].includes(deleted.status()), '即使驗收中斷也必須清除合成案件').toBe(true);
    const missing = await page.request.get(`/api/v1/cases/${id}`);
    expect(missing.status()).toBe(404);
  }
  expect(page.__liveUnexpectedErrors, '不得出現未處理例外或非預期 console 錯誤').toBe(0);
});

test('真實免費模型、引導選擇、PDF、錯誤重試、保守拒答與摘要保存', async ({ page }) => {
  await assertHealth(page);
  let patchRequests = 0;
  let browserMessageRequests = 0;
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (/^\/api\/v1\/cases\/[^/]+$/.test(path) && request.method() === 'PATCH') patchRequests += 1;
    if (/^\/api\/v1\/cases\/[^/]+\/messages$/.test(path) && request.method() === 'POST') browserMessageRequests += 1;
  });

  await page.goto('/?service=api#triage');
  await page.getByRole('button', { name: '描述我的狀況', exact: true }).click();
  await page.getByLabel('描述就醫情況', { exact: true }).fill('我因車禍住院三天，沒有手術，想準備文件。');
  const created = page.waitForResponse((response) => endpoint(response, '/api/v1/cases'));
  const suggested = page.waitForResponse((response) =>
    /^\/api\/v1\/cases\/[^/]+\/messages$/.test(new URL(response.url()).pathname)
    && response.request().method() === 'POST');
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  const createResponse = await created;
  expect(createResponse.status()).toBe(201);
  const initial = await createResponse.json();
  expect(typeof initial.id).toBe('string');
  page.__liveCaseIds.add(initial.id);
  const suggestionResponse = await suggested;
  expect(suggestionResponse.status()).toBe(200);
  const suggestion = (await suggestionResponse.json()).response;
  expect(suggestion.provider).toBe('grounded_rules');
  expect(suggestion.is_simulated).toBe(false);
  expect(suggestion.response_type).toBe('claim_suggestion');
  assertSources(suggestion.source_references);
  expect(suggestion.suggested_claim_types.some((entry) => entry.id === 'inpatient')).toBe(true);

  const picker = page.locator('fieldset.guided-type-picker');
  const build = page.getByRole('button', { name: '建立文件清單', exact: true });
  await expect(picker).toBeVisible();
  await expect(picker.locator('input[name="guided-claim-type"]:checked')).toHaveCount(0);
  await expect(build).toBeDisabled();
  const beforeChoice = await getCase(page, initial.id);
  expect(beforeChoice.claim_type_id).toBeNull();
  expect(beforeChoice.documents.length).toBe(0);
  await picker.getByRole('radio', { name: '住院醫療', exact: true }).check();
  await expect(picker.getByRole('radio', { name: '住院醫療', exact: true })).toBeChecked();
  await expect(build).toBeEnabled();
  expect(preparationSnapshot(await getCase(page, initial.id)) === preparationSnapshot(beforeChoice), '選取類型不可先寫入案件').toBe(true);
  expect(patchRequests).toBe(0);
  await assertLayout(page);

  const built = page.waitForResponse((response) => endpoint(response, `/cases/${initial.id}`, 'PATCH'));
  await build.click();
  const builtResponse = await built;
  expect(builtResponse.status()).toBe(200);
  const builtCase = await builtResponse.json();
  expect(builtCase.claim_type_id).toBe('inpatient');
  expect(builtCase.documents.length).toBeGreaterThan(0);
  expect(patchRequests).toBe(1);
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('cardif-claim-demo-cases-v1'))).toBeNull();

  // 使用現有合成文字 PDF；真正經上傳 HTTP、後端文字擷取與前端 canvas。
  const application = page.locator('article[data-document-id="application"]');
  await application.getByRole('button', { name: '上傳與檢查', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('模擬分析情境', { exact: true })).toHaveCount(0);
  await dialog.getByLabel('選擇文件', { exact: true }).setInputFiles(resolve('demo/documents/application-complete.pdf'));
  const analyzed = page.waitForResponse((response) => endpoint(response, `/cases/${initial.id}/documents/application/analyze`), { timeout: 100_000 });
  await dialog.getByRole('button', { name: '開始分析', exact: true }).click();
  const analysisResponse = await analyzed;
  expect(analysisResponse.status()).toBe(200);
  const analyzedCase = await analysisResponse.json();
  const document = analyzedCase.documents.find((entry) => entry.id === 'application');
  expect(document.analysis.provider).toBe('pdf_text');
  expect(document.analysis.is_simulated).toBe(false);
  expect(document.analysis.analysis_status).toBe('completed');
  expect(document.analysis.requires_human_review).toBe(true);
  expect(document.status).toBe('needs_attention');
  for (const name of ['insured_name', 'application_date']) {
    const field = document.analysis.extracted_fields.find((entry) => entry.field === name);
    expect(field?.value === '已辨識內容（隱私遮罩）', '真實擷取欄位必須存在且經過遮罩').toBe(true);
    expect(field.confidence).toBeGreaterThanOrEqual(0.8);
  }
  await expect(dialog.getByRole('heading', { name: '分析結果', exact: true })).toBeVisible();
  await assertRenderedPDF(dialog);
  await assertLayout(page);
  const confirmed = page.waitForResponse((response) => endpoint(response, `/cases/${initial.id}/documents/application`, 'PATCH'));
  await dialog.getByRole('button', { name: '我已人工確認', exact: true }).first().click();
  const confirmResponse = await confirmed;
  expect(confirmResponse.status()).toBe(200);
  const confirmedDocument = (await confirmResponse.json()).documents.find((entry) => entry.id === 'application');
  expect(confirmedDocument.confirmed_findings.length).toBe(1);
  expect(confirmedDocument.analysis.findings.length).toBe(document.analysis.findings.length);
  expect(confirmedDocument.status).toBe('needs_attention');
  await expect(dialog.getByRole('button', { name: '已人工確認', exact: true })).toBeDisabled();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(application).toContainText('需要補充或人工確認');

  await page.getByRole('button', { name: '開啟助手', exact: true }).click();
  const thread = page.getByRole('log', { name: '工作區對話', exact: true });
  const chat = page.getByLabel('詢問文件準備問題', { exact: true });
  const beforeFailure = await getCase(page, initial.id);
  const threadBeforeFailure = await thread.textContent();
  const messagesURL = `${apiOrigin}/api/v1/cases/${initial.id}/messages`;
  page.__liveExpected503URL = messagesURL;
  let injectedRequests = 0;
  const inject503 = async (route) => {
    injectedRequests += 1;
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'LLM_PROVIDER_ERROR', message: injectedFailureMessage } }),
    });
  };
  await page.route(messagesURL, inject503);
  await chat.fill(evidenceQuestion);
  const failed = page.waitForResponse((response) => endpoint(response, `/cases/${initial.id}/messages`));
  await page.getByRole('button', { name: '送出問題', exact: true }).click();
  expect((await failed).status()).toBe(503);
  await expect(page.getByRole('alert')).toContainText(injectedFailureMessage);
  expect(injectedRequests).toBe(1);
  const afterFailure = await getCase(page, initial.id);
  expect(JSON.stringify(afterFailure) === JSON.stringify(beforeFailure), '對話失敗不可改案或產生假成功訊息').toBe(true);
  expect(await thread.textContent() === threadBeforeFailure, '對話失敗不可在畫面產生假成功回答').toBe(true);
  await expect(chat).toHaveValue(evidenceQuestion);
  await assertLayout(page);
  await page.unroute(messagesURL, inject503);

  // 這是此尺寸唯一的外部模型請求；重試走真 API，不以 route 偽造成功。
  const answered = page.waitForResponse((response) => endpoint(response, `/cases/${initial.id}/messages`), { timeout: 55_000 });
  await page.getByRole('button', { name: '重試', exact: true }).click();
  const answerResponse = await answered;
  const result = await answerResponse.json();
  const errorCode = typeof result.error?.code === 'string' && /^[A-Z][A-Z0-9_]{0,63}$/.test(result.error.code)
    ? result.error.code : 'NO_SAFE_ERROR_CODE';
  expect(answerResponse.status(), `移除單次故障後必須由真實後端回覆成功；error_code=${errorCode}`).toBe(200);
  const answer = result.response;
  expect(answer.provider).toBe('openai_compatible');
  expect(answer.is_simulated).toBe(false);
  expect(answer.response_type).toBe('answer');
  expect(Object.keys(answer.proposed_case_updates).length).toBe(0);
  expect(answer.requires_human_review).toBe(true);
  assertSources(answer.source_references);
  expect(typeof answer.message === 'string' && answer.message.trim().length > 0, '模型必須提供非空的已驗證準備說明').toBe(true);
  const quotedSurgeryEvidence = surgeryEvidence.filter((entry) => answer.message.includes(entry.text));
  expect(quotedSurgeryEvidence.length, '回答必須保留至少一個完整的已查核手術文件條件段落').toBeGreaterThan(0);
  for (const evidence of quotedSurgeryEvidence) {
    expect(answer.source_references.some((reference) => reference.source_id === evidence.source_id
      && reference.page_number === evidence.page_number), '手術條件段落必須附上對應來源及頁碼').toBe(true);
  }
  expect(preparationSnapshot(result.case) === preparationSnapshot(beforeFailure), '模型回答不得改寫案件或文件需求').toBe(true);
  expect(result.case.messages.length).toBe(beforeFailure.messages.length + 2);
  const latestAnswer = thread.locator('.bubble:not(.user)').last();
  await expect.poll(async () => (await latestAnswer.textContent()).includes(answer.message), { message: '工作區最新回答必須顯示真 API 回覆；失敗輸出不含原始對話' }).toBe(true);
  await expect(page.getByRole('alert')).toHaveCount(0);
  for (const reference of answer.source_references) {
    expect(await latestAnswer.locator('a').evaluateAll((links, href) => links.some((link) => link.href === href), reference.official_url), '最新回答必須顯示自己的官方來源連結').toBe(true);
  }
  expect(browserMessageRequests, '瀏覽器僅可發送分類、一次受控失敗及一次真正重試').toBe(3);
  await assertHealth(page, { verified: true });
  await assertLayout(page);

  for (const refusal of [
    { message: '火星旅遊太空船票如何預訂', unknown: true },
    { message: '我的理賠資格一定符合嗎？賠多少錢？', unknown: false },
  ]) {
    const before = await getCase(page, initial.id);
    const response = await page.request.post(`/api/v1/cases/${initial.id}/messages`, {
      headers: originHeaders, data: { message: refusal.message },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.response.provider).toBe('grounded_rules');
    expect(body.response.is_simulated).toBe(false);
    expect(body.response.response_type).toBe('uncertain');
    expect(body.response.requires_human_review).toBe(true);
    expect(Object.keys(body.response.proposed_case_updates).length).toBe(0);
    expect(body.response.suggested_claim_types.length).toBe(0);
    assertSources(body.response.source_references, { allowEmpty: refusal.unknown });
    if (refusal.unknown) {
      expect(body.response.source_references.length).toBe(0);
      expect(body.response.message.includes('目前的官方資料沒有足夠依據'), '無來源問題必須明確告知資訊不足').toBe(true);
    } else {
      expect(body.response.source_references.every((source) => source.source_id === 'cardif-claims')).toBe(true);
      expect(body.response.message.includes('目前無法確認個別保單的理賠資格'), '不得推定資格或給付額度').toBe(true);
    }
    expect(body.response.message.includes('0800-012-899'), '拒答須提供已查核官方確認窗口').toBe(true);
    expect(preparationSnapshot(body.case) === preparationSnapshot(before), '保守拒答不得改寫案件或文件狀態').toBe(true);
    expect(body.case.messages.length).toBe(before.messages.length + 2);
  }

  await page.getByRole('button', { name: '查看準備摘要', exact: true }).click();
  await expect(page.getByRole('heading', { name: '送件前準備摘要', exact: true })).toBeVisible();
  await expect(page.getByRole('table')).toContainText('需要補充或人工確認');
  await assertLayout(page);
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: '下載摘要', exact: true }).click();
  const download = await downloaded;
  expect(await download.failure()).toBeNull();
  const summary = await readFile(await download.path(), 'utf8');
  expect(summary.includes('住院醫療') && summary.includes('需要補充或人工確認'), '下載摘要必須含實際案件準備狀態').toBe(true);
  expect(summary.includes('不是理賠核准') && summary.includes('https://life.cardif.com.tw/zh/a314'), '摘要須保留官方程序及非核准提醒').toBe(true);
  const saved = await getCase(page, initial.id);
  await page.reload();
  await expect(page.getByRole('heading', { name: '送件前準備摘要', exact: true })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('cardif-active-api-v1')) === initial.id, '重整後必須保留原 API 案件').toBe(true);
  expect(JSON.stringify(await getCase(page, initial.id)) === JSON.stringify(saved), '重整不可改寫已保存的案件').toBe(true);
  await page.getByRole('button', { name: '返回工作區', exact: true }).click();
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  await application.getByRole('button', { name: '查看檢查結果', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('button', { name: '已人工確認', exact: true })).toBeDisabled();
  await page.keyboard.press('Escape');
  await assertLayout(page);

  await page.locator('details.case-options > summary').click();
  page.once('dialog', (confirmation) => confirmation.accept());
  const deleted = page.waitForResponse((response) => endpoint(response, `/cases/${initial.id}`, 'DELETE'));
  await page.getByRole('button', { name: '清除測試案件', exact: true }).click();
  expect((await deleted).status()).toBe(200);
  await expect(page).toHaveURL(/#triage$/);
  expect((await page.request.get(`/api/v1/cases/${initial.id}`)).status()).toBe(404);
  page.__liveCaseIds.delete(initial.id);
  expect(await page.evaluate(() => sessionStorage.getItem('cardif-active-api-v1'))).toBeNull();
  expect(browserMessageRequests).toBe(3);
});
