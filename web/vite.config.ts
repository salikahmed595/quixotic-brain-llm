import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// PRD §11: React + TypeScript + Tailwind (Vite). The FastAPI backend serves the built files from web/dist
// (QB_FRONTEND_DIR); in development the Vite server forwards API calls to it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { '/v1': 'http://localhost:8000' } },
  build: { outDir: 'dist', emptyOutDir: true },
});
