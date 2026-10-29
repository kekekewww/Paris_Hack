import config from './playwright.config.js';

export default {
  ...config,
  testMatch: 'runtime-key-e2e.spec.js',
  outputDir: '.local/runtime-key-browser-results',
  reporter: [['list']],
  retries: 0,
  use: { ...config.use, baseURL: 'http://127.0.0.1:5176', trace: 'off', screenshot: 'off', video: 'off' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5176 --strictPort',
    url: 'http://127.0.0.1:5176',
    reuseExistingServer: false,
    timeout: 30_000,
  },
};
