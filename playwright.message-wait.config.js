import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

// 此設定只啟動專用 localhost 前端；測試攔截全部 API，不啟後端或呼叫模型。
const chrome = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
if (!existsSync(chrome)) throw new Error('請以 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH 指定已安裝的 Chromium。');
process.env.PLAYWRIGHT_NO_COPY_PROMPT = '1';

export default defineConfig({
  testDir: './tests',
  testMatch: 'message-wait.spec.js',
  outputDir: 'test-results-message-wait',
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 8_000 },
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5176',
    headless: true,
    launchOptions: { executablePath: chrome },
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
  projects: [
    { name: 'controlled-desktop-1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'controlled-mobile-390', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5176 --strictPort',
    url: 'http://127.0.0.1:5176',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
