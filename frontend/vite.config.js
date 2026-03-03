import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/static/dashboard/',
  build: {
    outDir: '../app/static/dashboard',
    emptyOutDir: true,
  },
})
