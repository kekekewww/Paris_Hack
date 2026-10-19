import { defineConfig } from '@playwright/test';

if (!process.env.CLAIM_API_BASE_URL) {
  throw new Error('連續引導驗收必須設定 CLAIM_API_BASE_URL；不會自動啟動伺服器。');
}
let target;
try {
  target = new URL(process.env.CLAIM_API_BASE_URL);
} catch {
  throw new Error('CLAIM_API_BASE_URL 必須是完整的 HTTP 或 HTTPS 網站根網址。');
}
if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password
    || target.pathname !== '/' || target.search || target.hash) {
  throw new Error('CLAIM_API_BASE_URL 必須是無帳密、路徑、查詢或片段的 HTTP 或 HTTPS 網站根網址。');
}
// Playwright 1.56 的失敗 DOM 快照也可能包含對話，與 trace 一併停用。
process.env.PLAYWRIGHT_NO_COPY_PROMPT = '1';

export default defineConfig({
  testDir: './tests',
  testMatch: 'assistant-followup-e2e.spec.js',
  outputDir: 'test-results-followup',
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: target.origin,
    headless: true,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  projects: [
    { name: 'followup-desktop-1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'followup-tablet-768', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'followup-mobile-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  // Mock 與 API 都使用指定網站；不建立 server、不讀取 .env、不安裝套件。
});
