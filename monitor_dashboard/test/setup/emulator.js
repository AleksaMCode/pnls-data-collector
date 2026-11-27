// Points the dashboard's Firebase module at the emulator, before any test file imports it.
import { afterEach, beforeEach, inject, vi } from 'vitest';
import { clearDatabase } from '../support/emulator';

vi.stubEnv(
  'VITE_FIREBASE_DATABASE_EMULATOR_HOST',
  inject('databaseEmulatorHost'),
);
vi.stubEnv('VITE_FIREBASE_AUTH_EMULATOR_HOST', inject('authEmulatorHost'));

beforeEach(async () => {
  await clearDatabase(inject('databaseEmulatorHost'));
});

afterEach(() => {
  vi.useRealTimers();
});
