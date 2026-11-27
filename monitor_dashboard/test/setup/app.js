// Setup for the integration tests: the whole app runs, with Firebase and the stats API faked.
import { configure } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, beforeEach, vi } from 'vitest';
import { fakeAuth } from '../support/fakeFirebase/auth';
import { fakeDatabase } from '../support/fakeFirebase/database';
import { parisInstant } from '../support/paris';
import { resetStatsApi, server, TODAY } from '../support/statsApi';

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

afterEach(() => {
  server.resetHandlers();
  resetStatsApi();
  fakeAuth.reset();
  fakeDatabase.reset();
  vi.useRealTimers();
});

afterAll(() => {
  server.close();
});
