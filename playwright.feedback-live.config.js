import { defineConfig } from '@playwright/test';

// 此組只驗收已另行啟動的真 API／指定模型；不載入環境檔或啟動服務。
if (process.env.LIVE_OPENROUTER !== '1') {
  throw new Error('組員回饋真實驗收必須明確設定 LIVE_OPENROUTER=1。');
}
if (!process.env.CLAIM_API_BASE_URL) {
  throw new Error('組員回饋真實驗收必須設定 CLAIM_API_BASE_URL；不會自動啟動伺服器。');
}
let target;
try {
  target = new URL(process.env.CLAIM_API_BASE_URL);
} catch {
  throw new Error('CLAIM_API_BASE_URL 必須是完整 HTTP 或 HTTPS 網站根網址。');
}
if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password
    || target.pathname !== '/' || target.search || target.hash) {
  throw new Error('CLAIM_API_BASE_URL 必須是無帳密、路徑、查詢或片段的 HTTP 或 HTTPS 網站根網址。');
}

// Playwright 1.56 預設失敗 DOM 會含對話；此組禁止保存該診斷及媒體。
process.env.PLAYWRIGHT_NO_COPY_PROMPT = '1';

export default defineConfig({
  testDir: './tests',
  testMatch: 'feedback-live.spec.js',
  outputDir: '.local/fixes-20261026/feedback-live-results',
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  repeatEach: 1,
  // 每尺寸硬上限 8 則訊息；各則可等 330 秒，另留操作及清理時間。
  timeout: 2_880_000,
  expect: { timeout: 20_000 },
  reporter: [['list']],
  use: {
    baseURL: target.origin,
    headless: true,
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  projects: [
    { name: 'feedback-desktop-1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'feedback-tablet-768', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'feedback-mobile-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  // 刻意不設 webServer、globalSetup、dotenv、HAR 或任何自動重試。
});
