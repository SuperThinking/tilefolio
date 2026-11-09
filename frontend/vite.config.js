import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Dev: `npm run dev` on :5173 proxies /api to the FastAPI backend on 127.0.0.1:8000.
// GitHub Pages build: VITE_BASE=/<repo>/ VITE_API_BASE=https://<backend-host> npm run build
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [svelte()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  preview: { host: '127.0.0.1' },
  build: { target: 'es2020', outDir: 'dist', emptyOutDir: true },
});
