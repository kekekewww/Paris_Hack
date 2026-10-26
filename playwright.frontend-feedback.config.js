import config from './playwright.config.js';

export default {
  ...config,
  testMatch:'frontend-feedback-e2e.spec.js',
  reporter:[['list']],
  outputDir:'.local/fixes-20261026/frontend-feedback-results',
};
