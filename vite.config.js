import { defineConfig } from 'vite';

export default defineConfig({
  optimizeDeps: { include: ['pdfjs-dist'] },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
    watch: { ignored: ['**/test-results*/**', '**/playwright-report*/**', '**/.venv/**', '**/.local/**', '**/backend/**', '**/demo/**', '**/public/pdfjs/**'] },
  },
});
