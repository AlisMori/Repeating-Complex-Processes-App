import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // Vitest scans the whole project by default and picks up
    // anything matching *.test.js / *.spec.js, including the
    // existing src/api/axios.test.js and
    // src/services/activityTracker.test.js. Those are written for
    // Node's native test runner (node:test), not Vitest. Scope
    // Vitest to the component specs so each runner owns its files.
    include: ['tests/unit/**/*.spec.js'],
  },
})
