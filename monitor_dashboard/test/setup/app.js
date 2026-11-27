// Setup for the integration tests: the whole app runs, with Firebase and the stats API faked.
import { cleanup, configure } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, beforeEach, vi } from 'vitest';
import { fakeAuth } from '../support/fakeFirebase/auth';
import { fakeDatabase } from '../support/fakeFirebase/database';
import { parisInstant } from '../support/paris';
import {
  resetStatsApi,
  server,
  settleStatsApi,
  TODAY,
} from '../support/statsApi';

vi.mock('firebase/app', () => import('../support/fakeFirebase/app'));
vi.mock('firebase/auth', () => import('../support/fakeFirebase/auth'));
vi.mock('@firebase/database', () => import('../support/fakeFirebase/database'));
// Leaflet needs a real layout and canvas; the stand-ins render the map's data as plain elements.
vi.mock('react-leaflet', () => import('../support/reactLeafletStub'));
vi.mock('leaflet.heat', () => import('../support/leafletHeatStub'));

// The whole MUI app renders slowly in jsdom, well past Testing Library's 1-second default.
configure({ asyncUtilTimeout: 5000 });

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

beforeEach(() => {
  // Only Date is frozen; timers stay real, so React, MSW and Testing Library run normally.
  vi.setSystemTime(parisInstant(`${TODAY}T10:00:00`));
});

afterEach(async () => {
  // Unmounts the app first, so it starts no more requests, then lets the ones it started finish
  // before the next test. This runs before the cleanup in dom.js, as Vitest runs the afterEach
  // hooks in reverse order.
  cleanup();
  try {
    await settleStatsApi();
  } finally {
    // Also when a request is still pending, so the next test doesn't inherit this one's routes,
    // data or clock. The settling error, if any, still fails this test.
    server.resetHandlers();
    resetStatsApi();
    fakeAuth.reset();
    fakeDatabase.reset();
    vi.useRealTimers();
  }
});

afterAll(() => {
  server.close();
});
