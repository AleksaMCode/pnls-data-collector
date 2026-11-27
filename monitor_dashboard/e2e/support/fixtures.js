import { test as base, expect } from '@playwright/test';
import {
  clearDatabase,
  pushValue,
  setValue,
} from '../../test/support/emulator.js';
import { state, TEST_USER } from './state.js';

/** "YYYY-MM-DD HH:MM:SS" in Paris, the format the collector writes. */
export function parisWallTime(date = new Date()) {
  return date.toLocaleString('sv-SE', { timeZone: 'Europe/Paris' });
}

/** Writes to the Realtime Database emulator as a capture device would. */
export const devices = {
  get host() {
    return state().databaseEmulatorHost;
  },
  node(device) {
    const today = new Date().toLocaleDateString('en-CA', {
      timeZone: 'Europe/Paris',
    });
    return `${device}-${today}`;
  },
  heartbeat(device, date = new Date()) {
    return setValue(this.host, `${this.node(device)}/status`, {
      timestamp: parisWallTime(date),
    });
  },
  probe(device, ssid) {
    return pushValue(this.host, `${this.node(device)}/data`, {
      ssid,
      timestamp: parisWallTime(),
    });
  },
};

export const test = base.extend({
  // Keeps the tests hermetic: map tiles and images from the internet are never fetched.
  page: async ({ page }, use) => {
    await page.route(
      /^https?:\/\/(?!localhost[:/]|127\.0\.0\.1[:/])/,
      (route) => route.abort(),
    );
    await use(page);
  },
  // Every test starts with no device data in Firebase.
  firebaseData: [
    async ({}, use) => {
      await clearDatabase(devices.host);
      await use();
    },
    { auto: true },
  ],
});

export async function signIn(page) {
  await page.goto('/login');
  await page.getByPlaceholder('name@email.com').fill(TEST_USER.email);
  await page.getByPlaceholder('********').fill(TEST_USER.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/home$/);
}

/** The stat card with a title and interval caption. */
export function statCard(page, title, interval) {
  return page
    .locator('.MuiCard-root')
    .filter({ has: page.getByRole('heading', { name: title, exact: true }) })
    .filter({ has: page.getByText(interval, { exact: true }) });
}

export function liveSwitch(page) {
  return page.getByRole('switch', {
    name: 'Toggle to view live Probe Request data',
  });
}

export { expect };
