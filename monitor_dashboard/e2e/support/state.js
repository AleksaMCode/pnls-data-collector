import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const PREVIEW_PORT = 4173;
export const STATE_FILE = fileURLToPath(
  new URL('../.state.json', import.meta.url),
);

/** The user the global setup creates in the Authentication emulator. */
export const TEST_USER = {
  email: 'e2e.viewer@example.test',
  password: 'e2e-password',
};

/** The addresses the global setup saved: the stats API and the emulators. */
export function state() {
  return JSON.parse(readFileSync(STATE_FILE, 'utf8'));
}
