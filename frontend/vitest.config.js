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
    // src/services/activityTracker.test.js, which are written for
    // Node's native test runner (node:test), not Vitest. Vitest
    // can't find describe/it blocks in those (different API
    // entirely), producing "No test suite found" failures. Scope
    // Vitest to only the new component specs so the two test
    // runners stay separate, each running its own files via its
    // own script (npm test for Node's runner, npm run test:unit
    // for Vitest).
    include: ['tests/unit/**/*.spec.js', 'tests/integration/**/*.spec.js'],
  }
})
