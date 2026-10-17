import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const apiBaseURL = process.env.CLAIM_API_BASE_URL || 'http://127.0.0.1:8000';
const originHeaders = { Origin: new URL(apiBaseURL).origin };

test('情境 G：明確注入官方 PDF 載入失敗後，實際 API 案件與摘要仍可使用', async ({ page }, testInfo) => {
  let caseId;
  const mainPageErrors = [];
  page.on('pageerror', (error) => mainPageErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') mainPageErrors.push(message.text());
  });
  try {
    const health = await page.request.get('/api/v1/health');
    expect(health.status()).toBe(200);
    expect((await health.json()).service_mode).toBe('api');
    await page.goto('/?service=api#triage');
    await page.getByRole('button', { name: '開始搜尋', exact: true }).click();
    await page.getByRole('button', { name: '住院醫療', exact: true }).click();
    await page.getByLabel('事故原因', { exact: true }).selectOption('illness');
    await page.getByLabel('是否接受手術', { exact: true }).selectOption('no');
    await page.getByLabel('收據用途', { exact: true }).selectOption('actual');
    const created = page.waitForResponse((response) =>
      new URL(response.url()).pathname === '/api/v1/cases' && response.request().method() === 'POST');
    await page.getByRole('button', { name: '建立文件清單', exact: true }).click();
    const creation = await created;
    expect(creation.status()).toBe(201);
    const originalCase = await creation.json();
    caseId = originalCase.id;
    await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
    await expect(page.locator('.mode-label').first()).toContainText('API');
    const article = page.locator('article[data-document-id="application"]');
    await article.getByText('文件說明與官方來源', { exact: true }).click();
    const officialLink = article.getByRole('link', { name: '開啟官方空白表單', exact: false });
    const href = await officialLink.getAttribute('href');
    expect(href).toMatch(/^https:\/\/life\.cardif\.com\.tw\/documents\//);

    // 只對外部官方 PDF 導航注入失敗；不替換任何 FastAPI 回應。
    // 這不表示官方站台目前真的故障，也不將失敗當作來源查核結果。
    await page.context().route((url) => url.href === href, (route) => route.abort('failed'));
    const failedRequest = page.context().waitForEvent('requestfailed', {
      predicate: (request) => request.url() === href,
    });
    const opened = page.waitForEvent('popup');
    await officialLink.click();
    const popup = await opened;
    const failure = await failedRequest;
    expect(failure.failure()?.errorText).toContain('ERR_FAILED');
    expect(failure.frame().page()).toBe(popup);
    expect(popup.isClosed()).toBe(false);
    await popup.screenshot({ path: testInfo.outputPath('injected-official-pdf-failure.png') });
    await popup.close();

    await expect(page).toHaveURL(/#workspace$/);
    await expect(page.getByRole('heading', { name: '文件準備工作區', exact: true })).toBeVisible();
    const persisted = await page.request.get(`/api/v1/cases/${caseId}`);
    expect(persisted.status()).toBe(200);
    expect(await persisted.json()).toEqual(originalCase);
    await page.getByRole('button', { name: '查看準備摘要', exact: true }).click();
    await expect(page.getByRole('heading', { name: '送件前準備摘要', exact: true })).toBeVisible();
    await expect(page.getByRole('table')).toContainText('尚未準備');
    await expect(page.getByRole('link', { name: /官方理賠資訊/ }).first()).toBeVisible();
    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: '下載摘要', exact: true }).click();
    const download = await downloading;
    expect(await download.failure()).toBeNull();
    const text = await readFile(await download.path(), 'utf8');
    expect(text).toContain('住院醫療');
    expect(text).toContain('尚未準備');
    expect(text).toMatch(/不.*理賠核准/);
    expect((await page.request.get(`/api/v1/cases/${caseId}`)).status()).toBe(200);
    await page.screenshot({ path: testInfo.outputPath('summary-after-injected-link-failure.png'), fullPage: true });
    expect(mainPageErrors).toEqual([]);
  } finally {
    if (caseId) {
      const deleted = await page.request.delete(`/api/v1/cases/${caseId}`, { headers: originHeaders });
      expect([200, 404]).toContain(deleted.status());
    }
  }
});
