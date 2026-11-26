import { defineConfig } from 'vite'
import reactOx from '@vitejs/plugin-react-oxc'

export default defineConfig({
  plugins: [reactOx()],
  resolve: {
    alias: {
      '@': (import.meta as any).dirname + '/src',
    },
  },
  server: {
    port: 5173,
    allowedHosts: ['hardened-desktop-darn.ngrok-free.dev', 'localhost'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
