import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // Vitest scans the whole project by default and picks up
    // anything matching *.test.js / *.spec.js — including the
    // existing src/api/axios.test.js and
    // src/services/activityTracker.test.js, which are written for
    // Node's native test runner (node:test), not Vitest. Vitest
    // can't find describe/it blocks in those (different API
    // entirely), producing "No test suite found" failures. Scope
    // Vitest to only the new component specs so the two test
    // runners stay separate, each running its own files via its
    // own script (npm test for Node's runner, npm run test:unit
    // for Vitest).
    include: ['tests/unit/**/*.spec.js'],
  }
})