import { defineConfig } from '@playwright/test';

// 這組驗收會使用後端已設定的真實模型；禁止日常測試意外啟動。
if (process.env.LIVE_OPENROUTER !== '1') {
  throw new Error('OpenRouter 真實驗收必須明確設定 LIVE_OPENROUTER=1。');
}
if (!process.env.CLAIM_API_BASE_URL) {
  throw new Error('OpenRouter 真實驗收必須設定 CLAIM_API_BASE_URL；不會自動啟動伺服器。');
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
// 專案鎖定的 Playwright 1.56 會另存失敗時的 DOM；關閉此含對話的診斷快照。
process.env.PLAYWRIGHT_NO_COPY_PROMPT = '1';

export default defineConfig({
  testDir: './tests',
  testMatch: 'openrouter-e2e.spec.js',
  outputDir: 'test-results-openrouter',
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  // 四輪真語意引導加一次真文件問答，每輪可等330秒，另保留清理預算。
  timeout: 1_800_000,
  expect: { timeout: 20_000 },
  reporter: [['list']],
  use: {
    baseURL: target.origin,
    headless: true,
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    // Trace/HAR/影片可能含對話、回覆或 session cookie；此組不保存這些資料。
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  projects: [
    { name: 'openrouter-desktop-1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'openrouter-tablet-768', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'openrouter-mobile-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  // 有意不設定 webServer，也不載入 .env 或安裝任何相依套件。
});
