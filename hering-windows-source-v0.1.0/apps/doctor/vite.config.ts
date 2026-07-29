import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  base: '/doctor/',
  plugins: [react()],
  build: { outDir: '../../services/api/static/doctor', emptyOutDir: true },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.ts' },
})

