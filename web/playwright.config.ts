import { defineConfig } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';

// PRD §13 AT-08: visual regression of the home screen against the two §4 reference screenshots, run against a running
// local stack (API on :8000 serving web/dist). Test-account credentials come from the environment, or from the
// gitignored web/.env.visual (KEY=value lines); they are never written into the repository.
const envFile = new URL('./.env.visual', import.meta.url);
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
  }
}

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.QA_BASE_URL || 'http://localhost:8000',
    browserName: 'chromium',
    deviceScaleFactor: 1,
    colorScheme: 'light',
    locale: 'en-US',
    timezoneId: 'UTC',
    trace: 'retain-on-failure',
  },
});
