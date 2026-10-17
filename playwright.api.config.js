import { defineConfig } from '@playwright/test';

const baseURL = process.env.CLAIM_API_BASE_URL || 'http://127.0.0.1:8000';
const python = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python';

export default defineConfig({
  testDir: './tests',
  testMatch: 'api-e2e.spec.js',
  outputDir: 'test-results-api',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  // 本機 RapidOCR 明確採單工鎖；串行驗證功能，不把容量競爭混成結果失敗。
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-api', open: 'never' }]],
  use: {
    baseURL,
    headless: true,
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  projects: [
    { name: 'api-desktop-1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'api-tablet-768', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'api-mobile-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: process.env.CLAIM_API_SERVER_COMMAND || `${python} -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`,
    url: `${baseURL}/api/v1/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { RATE_LIMIT_REQUESTS: process.env.RATE_LIMIT_REQUESTS || '1000' },
  },
});
