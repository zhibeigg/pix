import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiProxyTarget = process.env.VITE_PIX_API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../../dist/web',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('i18next')) return 'i18n-vendor'
          if (id.includes('@radix-ui') || id.includes('react-remove-scroll') || id.includes('react-style-singleton') || id.includes('aria-hidden') || id.includes('@floating-ui') || id.includes('use-sidecar') || id.includes('use-callback-ref')) return 'radix-vendor'
          if (id.includes('node_modules/motion')) return 'motion-vendor'
          if (id.includes('qrcode')) return 'qr-vendor'
          if (id.includes('node_modules/react') || id.includes('node_modules/scheduler')) return 'react-vendor'
          return 'vendor'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
