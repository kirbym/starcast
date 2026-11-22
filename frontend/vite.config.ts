import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The root .env holds settings for both deployables.
  envDir: '..',
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    // The Kind Sprite tests apply the real stylesheet, so keep its contents.
    css: { include: [/index\.css/] },
    env: {
      TZ: 'America/Los_Angeles',
      VITE_API_BASE_URL: 'http://api.test',
    },
  },
})
