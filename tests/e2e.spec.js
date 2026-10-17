import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile } from 'node:fs/promises';

// 僅以公開操作驗證產品行為，不覆寫案件狀態或直接呼叫 UI 內部函式。
const syntheticPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1ioAAAAASUVORK5CYII=',
  'base64',
);

async function assertNoHorizontalOverflow(page) {
  const size = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
    dialog: (() => {
      const element = document.querySelector('dialog[open]');
      return element ? { width: element.clientWidth, content: element.scrollWidth } : null;
    })(),
  }));
  expect(size.content, '主畫面不應超出視窗而被裁切').toBeLessThanOrEqual(size.width + 1);
  if (size.dialog) expect(size.dialog.content, '文件檢查視窗不應出現橫向溢出').toBeLessThanOrEqual(size.dialog.width + 1);
}

async function waitForEntryMotion(page) {
  await page.evaluate(async () => {
    const finite = document.getAnimations().filter((animation) => animation.effect?.getComputedTiming().endTime !== Infinity);
    await Promise.all(finite.map((animation) => animation.finished.catch(() => {})));
  });
}

async function startDirectCase(page, claimType = '住院醫療') {
  await page.goto('/?service=mock#triage');
  await page.getByRole('button', { name: '開始搜尋', exact: true }).click();
  await expect(page).toHaveURL(/#search$/);
  await page.getByRole('button', { name: claimType, exact: true }).click();
  await page.getByLabel('事故原因', { exact: true }).selectOption('illness');
  await page.getByLabel('是否接受手術', { exact: true }).selectOption('no');
  await page.getByLabel('收據用途', { exact: true }).selectOption('actual');
  await page.getByRole('button', { name: '建立文件清單', exact: true }).click();
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  await expect(page.locator('article[data-document-id]').first()).toBeVisible();
}

async function openAnalysis(page) {
  const document = page.locator('article[data-document-id]').first();
  await document.getByRole('button', { name: '上傳與檢查', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: '文件初步檢查', exact: true })).toBeVisible();
  return dialog;
}

async function uploadSyntheticFile(dialog, scenario = 'missing') {
  await dialog.getByLabel('選擇文件', { exact: true }).setInputFiles({
    name: 'synthetic-claim.png',
    mimeType: 'image/png',
    buffer: syntheticPng,
  });
  await dialog.getByLabel('模擬分析情境', { exact: true }).selectOption(scenario);
  await dialog.getByRole('button', { name: '開始分析', exact: true }).click();
  await expect(dialog.getByText(/分析結果|分析完成|檢查結果/).first()).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.__claimConsoleErrors = errors;
});

test.afterEach(async ({ page }) => {
  expect(page.__claimConsoleErrors, '不得出現未處理的 JavaScript 或 console 錯誤').toEqual([]);
});

test('首頁雙入口、官方來源與原型聲明可操作', async ({ page }, testInfo) => {
  await page.goto('/?service=mock#triage');
  await expect(page.getByRole('button', { name: '開始使用', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '開始搜尋', exact: true })).toBeVisible();
  const official = page.getByRole('link', { name: /官方/ }).first();
  await expect(official).toHaveAttribute('href', /^https:\/\/life\.cardif\.com\.tw\//);
  await expect(page.getByText(/展示原型|概念原型|黑客松/).first()).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('landing.png'), fullPage: true });
  await page.getByRole('button', { name: '開始使用', exact: true }).click();
  await expect(page.getByLabel('描述就醫情況', { exact: true })).toBeVisible();
});

test('AI 引導確認類型後進入共用工作區並取得準備摘要', async ({ page }, testInfo) => {
  await page.goto('/?service=mock#triage');
  await page.getByRole('button', { name: '開始使用', exact: true }).click();
  await page.getByLabel('描述就醫情況', { exact: true }).fill('我上星期車禍住院三天，沒有接受手術，想準備理賠文件。');
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  await expect(page.getByRole('button', { name: '確認並建立清單', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '確認並建立清單', exact: true }).click();
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  await expect(page.locator('article[data-document-id]')).not.toHaveCount(0);
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('guided-workspace.png'), fullPage: true });
  await page.getByRole('button', { name: '查看準備摘要', exact: true }).click();
  await expect(page.getByRole('heading', { name: '送件前準備摘要', exact: true })).toBeVisible();
  await expect(page.getByText(/尚未準備|尚待|待補|未完成/).first()).toBeVisible();
  await assertNoHorizontalOverflow(page);
  await page.getByRole('button', { name: '返回工作區', exact: true }).click();
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
});

test('資訊不足會先追問而不直接建立文件清單', async ({ page }) => {
  await page.goto('/?service=mock#assistant');
  await page.getByLabel('描述就醫情況', { exact: true }).fill('我想申請理賠，不知道怎麼開始。');
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  await expect(page.getByRole('log', { name: '引導對話', exact: true }).getByText(/請先確認.*住院.*門診/)).toBeVisible();
  await expect(page.getByRole('button', { name: '確認並建立清單', exact: true })).toHaveCount(0);
  await page.getByLabel('描述就醫情況', { exact: true }).fill('因為疾病住院三天，沒有接受手術。');
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  await expect(page.getByRole('button', { name: '確認並建立清單', exact: true })).toBeVisible();
});

test('送出引導後返回首頁，延遲回覆不會覆蓋目前畫面', async ({ page }) => {
  // 暫停計時器，確保導覽發生在 Mock 回覆之前，再推進兩段服務延遲。
  await page.clock.install({ time: new Date('2026-10-17T03:00:00Z') });
  await page.goto('/?service=mock#assistant');
  await expect(page.getByLabel('描述就醫情況', { exact: true })).toBeVisible();
  await waitForEntryMotion(page);
  await page.clock.pauseAt(new Date('2026-10-17T04:00:00Z'));
  await page.getByLabel('描述就醫情況', { exact: true }).fill('我因疾病住院三天，沒有手術。');
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  await page.getByRole('button', { name: '返回首頁', exact: true }).first().click();
  await expect(page).toHaveURL(/#triage$/);
  await page.clock.runFor(1000);
  await expect(page).toHaveURL(/#triage$/);
  await expect(page.getByRole('button', { name: '開始使用', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '讓我們協助您的理賠流程', exact: true })).not.toBeVisible();
});

for (const claimType of ['住院醫療', '醫療門診', '防癌或重大疾病']) {
  test(`快速選擇 ${claimType} 可建立案件並顯示尚未完成的摘要`, async ({ page }) => {
    await startDirectCase(page, claimType);
    await expect(page.getByText(claimType, { exact: true }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /官方/ }).first()).toHaveAttribute('href', /^https:\/\/life\.cardif\.com\.tw\//);
    await assertNoHorizontalOverflow(page);
    await page.getByRole('button', { name: '查看準備摘要', exact: true }).click();
    await expect(page.getByRole('heading', { name: '送件前準備摘要', exact: true })).toBeVisible();
    await expect(page.getByText(/尚未準備|尚待|待補|未完成/).first()).toBeVisible();
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: '下載摘要', exact: true }).click();
    const download = await downloaded;
    expect(download.suggestedFilename()).toMatch(/\.(json|txt|html|pdf)$/);
    expect(await download.failure()).toBeNull();
    const content = await readFile(await download.path(), 'utf8');
    expect(content).toContain(claimType);
    expect(content).toContain('https://life.cardif.com.tw/zh/a314');
    expect(content).toMatch(/不.*理賠核准/);
  });
}

test('上傳與 Mock 缺漏分析可預覽文件、查看問題並人工確認', async ({ page }, testInfo) => {
  await startDirectCase(page);
  const dialog = await openAnalysis(page);
  await uploadSyntheticFile(dialog, 'missing');
  await expect(dialog.locator('#analysis-results').getByText(/疑似|缺漏|待確認|需.*確認/).first()).toBeVisible();
  await expect(dialog.getByRole('button', { name: '我已人工確認', exact: true }).first()).toBeVisible();
  await expect(dialog.locator('img, object, iframe, canvas').first()).toBeVisible();
  await dialog.getByRole('button', { name: '查看欄位提醒 1', exact: true }).click();
  await expect(dialog.locator('[data-finding-id].selected')).toHaveCount(1);
  await assertNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('ocr-findings.png'), fullPage: true });
  await dialog.getByRole('button', { name: '我已人工確認', exact: true }).first().click();
  await expect(dialog.getByText(/已人工確認|已確認/).first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('article[data-document-id]').first()).toContainText(/需要補充|待確認|已上傳|初步檢查|已確認/);
});

test('Mock 完整文件只顯示初步檢查結果', async ({ page }) => {
  await startDirectCase(page);
  const dialog = await openAnalysis(page);
  await uploadSyntheticFile(dialog, 'complete');
  await expect(dialog.locator('#analysis-results').getByText(/未發現指定缺漏/).first()).toBeVisible();
  await expect(dialog.getByText(/不.*正式|不.*核准|不.*審核|非.*審核|仍.*人工|保險公司/).first()).toBeVisible();
  await expect(dialog.getByText(/理賠已核准|保證給付|正式審核通過/)).toHaveCount(0);
});

test('分析途中關閉視窗仍更新文件狀態且不產生程式錯誤', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-17T03:00:00Z') });
  await startDirectCase(page);
  const documentId = await page.locator('article[data-document-id]').first().getAttribute('data-document-id');
  const dialog = await openAnalysis(page);
  await dialog.getByLabel('選擇文件', { exact: true }).setInputFiles({
    name: 'background-analysis.png', mimeType: 'image/png', buffer: syntheticPng,
  });
  await page.clock.pauseAt(new Date('2026-10-17T04:00:00Z'));
  await dialog.getByRole('button', { name: '開始分析', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await page.clock.runFor(1000);
  await expect(page.locator(`article[data-document-id="${documentId}"]`)).toContainText('需要補充或人工確認');
  await expect(page.locator(`article[data-document-id="${documentId}"]`)).toContainText('background-analysis.png');
  await expect(page.getByText(/Cannot set properties|Cannot read properties|TypeError/)).toHaveCount(0);
});

test('重新選擇文件會清除舊分析，分析中不可更換輸入', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-17T03:00:00Z') });
  await startDirectCase(page);
  const dialog = await openAnalysis(page);
  await uploadSyntheticFile(dialog, 'missing');
  await expect(dialog.getByRole('button', { name: '我已人工確認', exact: true }).first()).toBeVisible();
  await page.clock.pauseAt(new Date('2026-10-17T04:00:00Z'));
  const file = dialog.getByLabel('選擇文件', { exact: true });
  const scenario = dialog.getByLabel('模擬分析情境', { exact: true });
  await file.setInputFiles({ name: 'second.png', mimeType: 'image/png', buffer: syntheticPng });
  await expect(dialog.locator('#analysis-results')).toBeEmpty();
  await expect(dialog.getByRole('button', { name: '我已人工確認', exact: true })).toHaveCount(0);
  await scenario.selectOption('complete');
  await dialog.getByRole('button', { name: '開始分析', exact: true }).click();
  await expect(file).toBeDisabled();
  await expect(scenario).toBeDisabled();
  await page.clock.runFor(1000);
  await expect(dialog.locator('#analysis-results').getByText(/未發現指定缺漏/).first()).toBeVisible();
  await expect(file).toBeEnabled();
  await expect(scenario).toBeEnabled();
});

test('Mock 模糊文件需保留辨識不確定性', async ({ page }) => {
  await startDirectCase(page);
  const dialog = await openAnalysis(page);
  await uploadSyntheticFile(dialog, 'blurred');
  await expect(dialog.locator('#analysis-results').getByText(/模糊|低信心|無法可靠|辨識.*不足/).first()).toBeVisible();
  await expect(dialog.locator('#analysis-results').getByText(/人工確認|重新上傳|清晰/).first()).toBeVisible();
});

test('不支援的檔案會被拒絕且可重新選擇', async ({ page }) => {
  await startDirectCase(page);
  const dialog = await openAnalysis(page);
  await dialog.getByLabel('選擇文件', { exact: true }).setInputFiles({
    name: 'unsupported.txt', mimeType: 'text/plain', buffer: Buffer.from('synthetic demo only'),
  });
  const analyze = dialog.getByRole('button', { name: '開始分析', exact: true });
  await expect(analyze).toBeDisabled();
  await expect(dialog.getByText(/PDF.*JPG|PDF.*PNG|格式.*不支援|不支援.*格式|格式不符/).first()).toBeVisible();
  await dialog.getByLabel('選擇文件', { exact: true }).setInputFiles({
    name: 'recovered.png', mimeType: 'image/png', buffer: syntheticPng,
  });
  await expect(analyze).toBeEnabled();
  await dialog.getByLabel('模擬分析情境', { exact: true }).selectOption('complete');
  await analyze.click();
  await expect(dialog.locator('#analysis-results').getByText(/未發現指定缺漏/).first()).toBeVisible();
});

test('超過 10 MB 的檔案會被拒絕', async ({ page }) => {
  await startDirectCase(page);
  const dialog = await openAnalysis(page);
  const oversized = Buffer.alloc(10 * 1024 * 1024 + 1);
  syntheticPng.copy(oversized);
  await dialog.getByLabel('選擇文件', { exact: true }).setInputFiles({
    name: 'oversized.png', mimeType: 'image/png', buffer: oversized,
  });
  const analyze = dialog.getByRole('button', { name: '開始分析', exact: true });
  await expect(analyze).toBeDisabled();
  await expect(dialog.getByText(/不可超過.*10|超過.*10.*MB|10.*MB.*限制/).first()).toBeVisible();
});

test('服務失敗顯示錯誤且重試能恢復對話', async ({ page }) => {
  await page.goto('/?service=mock&mock_error=message#assistant');
  await page.getByLabel('描述就醫情況', { exact: true }).fill('我因疾病住院三天，沒有手術。');
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  await expect(page.getByRole('button', { name: '重試', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '重試', exact: true }).click();
  await expect(page.getByRole('button', { name: '確認並建立清單', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '重試', exact: true })).toHaveCount(0);
});

test('重新整理保留案件，清除後移除準備資料', async ({ page }) => {
  await startDirectCase(page, '醫療門診');
  const firstDocument = page.locator('article[data-document-id]').first();
  const id = await firstDocument.getAttribute('data-document-id');
  await page.reload();
  await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
  await expect(page.locator(`article[data-document-id="${id}"]`)).toBeVisible();
  await expect(page.getByText('醫療門診', { exact: true }).first()).toBeVisible();
  page.on('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '清除測試案件', exact: true }).click();
  await expect(page.getByRole('button', { name: '開始使用', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '繼續準備', exact: true })).toHaveCount(0);
});

test('文件準備狀態可更新、保留並反映於摘要', async ({ page }) => {
  await startDirectCase(page);
  const required = page.locator('article[data-document-id]').first();
  const requiredId = await required.getAttribute('data-document-id');
  await expect(required.getByRole('option', { name: '我已確認此條件不適用', exact: true })).toHaveCount(0);
  await required.getByRole('combobox').selectOption('uploaded');
  await expect(page.locator(`article[data-document-id="${requiredId}"]`)).toContainText('已上傳／自行備妥');
  const conditional = page.locator('article[data-document-id]').filter({ hasText: '條件式' }).first();
  const conditionalId = await conditional.getAttribute('data-document-id');
  await conditional.getByRole('combobox').selectOption('not_applicable');
  await expect(page.locator(`article[data-document-id="${conditionalId}"]`)).toContainText('已確認不適用');
  await page.reload();
  await expect(page.locator(`article[data-document-id="${requiredId}"]`)).toContainText('已上傳／自行備妥');
  await page.getByRole('button', { name: '查看準備摘要', exact: true }).click();
  await expect(page.getByRole('table')).toContainText('已上傳／自行備妥');
  await expect(page.getByRole('table')).toContainText('已確認不適用');
});

test('工作區問答附官方來源並保留資格不確定性', async ({ page }) => {
  await startDirectCase(page);
  await page.getByLabel('詢問文件準備問題', { exact: true }).fill('我一定可以獲賠多少錢？');
  await page.getByRole('button', { name: '送出問題', exact: true }).click();
  const log = page.getByRole('log', { name: '工作區對話', exact: true });
  await expect(log.getByText(/無法確認.*資格|不能核准理賠/)).toBeVisible();
  await expect(log.getByRole('link').first()).toHaveAttribute('href', /^https:\/\/life\.cardif\.com\.tw\//);
});

test('惡意輸入以純文字顯示，不執行 HTML 事件', async ({ page }) => {
  await page.goto('/?service=mock#assistant');
  const injection = '<img src=x onerror="window.__claimXss=true">';
  await page.getByLabel('描述就醫情況', { exact: true }).fill(`我住院三天 ${injection}`);
  await page.getByRole('button', { name: '送出描述', exact: true }).click();
  await expect(page.getByText(`我住院三天 ${injection}`, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '確認並建立清單', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.__claimXss)).toBeUndefined();
  await expect(page.locator('img[src="x"]')).toHaveCount(0);
});

test('助手收合不阻礙文件操作，且鍵盤可關閉檢查視窗', async ({ page }) => {
  await startDirectCase(page);
  await page.getByRole('button', { name: '隱藏助手', exact: true }).click();
  const openAssistant = page.getByRole('button', { name: '開啟助手', exact: true });
  await expect(openAssistant).toBeVisible();
  await openAssistant.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: '隱藏助手', exact: true })).toBeVisible();
  const upload = page.locator('article[data-document-id]').first().getByRole('button', { name: '上傳與檢查', exact: true });
  await upload.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(upload).toBeFocused();
  await assertNoHorizontalOverflow(page);
});

test('首頁與文件工作區符合基本 WCAG A / AA 自動檢查', async ({ page }) => {
  await page.goto('/?service=mock#triage');
  await expect(page.getByRole('button', { name: '開始使用', exact: true })).toBeEnabled();
  await expect(page.getByRole('button', { name: '開始搜尋', exact: true })).toBeEnabled();
  await waitForEntryMotion(page);
  const landing = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(landing.violations.map(({ id, nodes }) => ({ id, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) }))).toEqual([]);
  await startDirectCase(page);
  await waitForEntryMotion(page);
  const workspace = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(workspace.violations.map(({ id, nodes }) => ({ id, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) }))).toEqual([]);
});
