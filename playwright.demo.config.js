import { defineConfig } from '@playwright/test';
import apiConfig from './playwright.api.config.js';

export default defineConfig({
  ...apiConfig,
  testMatch: 'demo-failure.spec.js',
  outputDir: 'test-results-demo',
  timeout: 60_000,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report-demo', open: 'never' }]],
  projects: [apiConfig.projects[0]],
});
