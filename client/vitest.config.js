import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'


export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    clearMocks: true,
    restoreMocks: true,
    pool: 'threads',
    maxWorkers: 1,
    fileParallelism: false,
    testTimeout: 10_000,
  },
})
