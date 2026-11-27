import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The devices, the collector and the stats API all run on Paris time, and so do most viewers. Tests that
// need another viewer timezone set it themselves (see test/support/timezone.js).
process.env.TZ = 'Europe/Paris';

// Values the app reads from import.meta.env. The stats API URL is never contacted: MSW answers it.
const env = {
  VITE_STATS_API_URL: 'http://stats-api.test',
  VITE_FIREBASE_API_KEY: 'test-api-key',
  VITE_FIREBASE_AUTH_DOMAIN: 'demo-pnls.firebaseapp.com',
  VITE_FIREBASE_DATABASE_URL: 'https://demo-pnls-default-rtdb.firebaseio.com',
  VITE_FIREBASE_PROJECT_ID: 'demo-pnls',
  VITE_FIREBASE_STORAGE_BUCKET: '',
  VITE_FIREBASE_MESSAGING_SENDER_ID: '',
  VITE_FIREBASE_APP_ID: '',
};

const jsdomProject = {
  extends: true,
  test: {
    environment: 'jsdom',
    setupFiles: ['test/setup/dom.js'],
  },
};

export default defineConfig({
  plugins: [react()],
  test: {
    env,
    // The default `forks` pool gives every test file its own process, so a test can change TZ safely.
    pool: 'forks',
    restoreMocks: true,
    unstubEnvs: true,
    // MUI X imports its own CSS files, which only Vite's pipeline can load.
    server: { deps: { inline: [/@mui\/x-/] } },
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx,ts,tsx}'],
      // Theme files are MUI template styling with no behavior to test.
      exclude: ['src/theme/**', 'src/**/*.test.{js,jsx}'],
      // Paths in lcov.info start at the repository root, as Codecov expects.
      reporter: ['text', 'html', ['lcov', { projectRoot: '..' }]],
    },
    projects: [
      {
        ...jsdomProject,
        test: {
          ...jsdomProject.test,
          name: 'unit',
          include: ['src/**/*.test.{js,jsx}'],
        },
      },
      {
        ...jsdomProject,
        test: {
          ...jsdomProject.test,
          name: 'integration',
          include: ['test/integration/**/*.test.{js,jsx}'],
          setupFiles: [...jsdomProject.test.setupFiles, 'test/setup/app.js'],
          testTimeout: 30_000,
        },
      },
      {
        extends: true,
        test: {
          name: 'emulator',
          environment: 'node',
          include: ['test/emulator/**/*.test.js'],
          globalSetup: ['test/setup/emulatorGlobal.js'],
          setupFiles: ['test/setup/emulator.js'],
          // Starting the emulator container can take a while on the first run (the image build).
          hookTimeout: 240_000,
          testTimeout: 30_000,
        },
      },
    ],
  },
});
