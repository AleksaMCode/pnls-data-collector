import { defineConfig, devices } from '@playwright/test';
import { PREVIEW_PORT } from './e2e/support/state.js';

// The end-to-end tests: the built dashboard in Chromium, against the stats API's Docker image, a
// Supabase Postgres and the Firebase emulators (see e2e/global-setup.js). They need Docker.
export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/global-setup.js',
  // The tests share one database and one Firebase emulator.
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PREVIEW_PORT}`,
    locale: 'en-US',
    timezoneId: 'Europe/Paris',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
