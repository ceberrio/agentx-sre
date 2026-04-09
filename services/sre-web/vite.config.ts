import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy target: in Docker, sre-agent is reachable as http://sre-agent:8000.
// For local dev (outside Docker), override with VITE_PROXY_TARGET env var.
const proxyTarget = process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
