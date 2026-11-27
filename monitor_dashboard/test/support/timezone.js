import { afterEach } from 'vitest';

const original = process.env.TZ;

/**
 * Runs the rest of the test as a viewer in another timezone. Node applies a TZ change at once, and
 * every test file runs in its own process (the `forks` pool), so other files never see it.
 */
export function useViewerTimezone(timeZone) {
  process.env.TZ = timeZone;
}

afterEach(() => {
  process.env.TZ = original;
});
