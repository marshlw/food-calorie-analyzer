import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Прокси не используется: клиент обращается к API по абсолютному
    // VITE_API_URL (кросс-origin разрешён через CORS на бэкенде).
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser',
  },
})
