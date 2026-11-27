// End-to-end tests: the built dashboard against the real stats API, Supabase Postgres and the Firebase
// emulators.
import { readFile } from 'node:fs/promises';
import { EXPECTED } from './support/seed.js';
import { state } from './support/state.js';
import {
  devices,
  expect,
  liveSwitch,
  signIn,
  statCard,
  test,
} from './support/fixtures.js';

const n = (value) => value.toLocaleString('en-US');

function deviceRow(page, device) {
  return page
    .getByRole('row')
    .filter({ has: page.getByRole('gridcell', { name: device, exact: true }) });
}

test.describe('signing in', () => {
  test('a signed-out viewer is sent to the sign-in page', async ({ page }) => {
    await page.goto('/home');

    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByText('Sign in to continue to the PNLS-DC Monitoring Dashboard'),
    ).toBeVisible();
  });

  test('wrong credentials are refused by Firebase', async ({ page }) => {
    await page.goto('/login');
    await page
      .getByPlaceholder('name@email.com')
      .fill('e2e.viewer@example.test');
    await page.getByPlaceholder('********').fill('not-the-password');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(
      page.getByText('Failed to sign in. Please try again.'),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('the session survives a reload, and signing out ends it', async ({
    page,
  }) => {
    await signIn(page);

    await page.reload();
    await expect(page).toHaveURL(/\/home$/);

    await page.getByRole('button', { name: 'Open menu' }).click();
    await page.getByRole('menuitem', { name: 'Logout' }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto('/home');
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe('stats API', () => {
  test('refuses requests without a valid Firebase ID token', async ({
    request,
  }) => {
    const { statsApiUrl } = state();

    expect((await request.get(`${statsApiUrl}/stats/total`)).status()).toBe(
      401,
    );
    expect(
      (
        await request.get(`${statsApiUrl}/stats/total`, {
          headers: { Authorization: 'Bearer not-a-token' },
        })
      ).status(),
    ).toBe(401);
    expect((await request.get(`${statsApiUrl}/health`)).status()).toBe(200);
  });
});

test.describe('home page', () => {
  test('shows the totals the stats API reads from Supabase', async ({
    page,
  }) => {
    await signIn(page);

    await expect(statCard(page, 'Probe Requests', 'Total')).toContainText(
      n(EXPECTED.totalProbeRequests),
    );
    await expect(statCard(page, 'SSIDs', 'Total (unique)')).toContainText(
      String(EXPECTED.uniqueSsids),
    );
    await expect(
      statCard(page, 'MAC addresses', 'Total (unique)'),
    ).toContainText(String(EXPECTED.uniqueMacs));
    await expect(
      statCard(page, 'Probe Requests', 'Last 30 days'),
    ).toContainText(String(EXPECTED.last30Probes));
  });

  test('lists the devices with their totals', async ({ page }) => {
    await signIn(page);

    for (const device of EXPECTED.devices) {
      await expect(deviceRow(page, device)).toBeVisible();
    }
    await expect(deviceRow(page, 'RPI-1')).toContainText(
      n(EXPECTED.rpi1ProbeRequests),
    );
    await expect(deviceRow(page, 'RPI-1')).toContainText(
      'Users Office (61/R-202)',
    );
  });

  test('marks a device online once it sends a heartbeat', async ({ page }) => {
    await devices.heartbeat('RPI-1');
    await devices.heartbeat('RPI-2', new Date(Date.now() - 30 * 60_000));
    await signIn(page);

    await expect(deviceRow(page, 'RPI-1')).toContainText('Online');
    await expect(deviceRow(page, 'RPI-2')).toContainText('Offline');
    await expect(deviceRow(page, 'RPI-3')).toContainText('Offline');
  });

  test('counts probe requests live as the devices write them', async ({
    page,
  }) => {
    await devices.probe('RPI-1', 'CERN');
    await devices.probe('RPI-2', 'eduroam');
    await signIn(page);
    const live = statCard(page, 'Probe Requests', 'Live');

    await liveSwitch(page).check();
    await expect(live).toContainText('2');

    // Written right away, also before the listeners have their first data; those count too.
    await devices.probe('RPI-1', 'Home_5G');
    await devices.probe('RPI-3', 'Cafe');
    await expect(live).toContainText('4');
    await expect(live).toContainText('+100.00%');
  });

  test('draws the manufacturer world map', async ({ page }) => {
    await signIn(page);

    await page.getByText('Manufacturer data', { exact: true }).click();

    await expect(
      page.getByRole('gridcell', { name: 'Apple, Inc.' }),
    ).toBeVisible();
    await expect(
      page.locator('path title', {
        hasText: /^United States of America: 5$|^United States: 5$/,
      }),
    ).toHaveCount(1);
  });
});

test.describe('device page', () => {
  test("shows the device's live SSIDs", async ({ page }) => {
    await signIn(page);
    await page.goto('/device/RPI-1');
    await expect(page.getByText('Device: RPI-1')).toBeVisible();

    await devices.probe('RPI-1', 'Seed-Network');
    await liveSwitch(page).check();
    const table = page.getByRole('table');
    // The latest row is the listener's first data, so once it shows, the rows below arrive live.
    await expect(
      table.getByRole('cell', { name: 'Seed-Network' }),
    ).toBeVisible();

    await devices.probe('RPI-1', 'CERN');
    await devices.probe('RPI-1', 'E2E-Network');

    await expect(
      table.getByRole('cell', { name: 'E2E-Network' }),
    ).toBeVisible();
    // CERN is filtered out by default.
    await expect(
      table.getByRole('cell', { name: 'CERN', exact: true }),
    ).toHaveCount(0);
  });
});

test.describe('SSID page', () => {
  test('searches and shows the locations of an SSID', async ({ page }) => {
    await signIn(page);
    await page.getByRole('button', { name: 'SSIDs' }).click();
    const grid = page.getByRole('grid');
    await expect(grid.getByRole('gridcell', { name: 'eduroam' })).toBeVisible();

    await page.getByPlaceholder('Search SSID...').fill('cer');
    await expect(grid.getByRole('row')).toHaveCount(3); // The header and two SSIDs.
    await expect(
      grid.getByRole('gridcell', { name: 'CERN-Guest' }),
    ).toBeVisible();

    await grid.getByRole('gridcell', { name: 'CERN', exact: true }).click();
    await expect(
      page.getByText('Showing 1 location(s) for "CERN".', { exact: false }),
    ).toBeVisible();
    await expect(page.locator('.leaflet-interactive')).toHaveCount(1);
  });

  test('downloads the SSIDs as CSV', async ({ page }) => {
    await signIn(page);
    await page.getByRole('button', { name: 'SSIDs' }).click();
    await expect(
      page.getByRole('grid').getByRole('gridcell', { name: 'eduroam' }),
    ).toBeVisible();

    const downloading = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download CSV' }).click();
    const download = await downloading;

    expect(download.suggestedFilename()).toMatch(/\.csv$/);
    const csv = await readFile(await download.path(), 'utf8');
    expect(csv.split(/\r?\n/)[0]).toBe('ssid,seen_count,first_seen,last_seen');
    expect(csv).toContain('eduroam,3,');
    await expect(
      page.getByText('SSID CSV downloaded successfully.'),
    ).toBeVisible();
  });
});

test.describe('small screens', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test.fail(
    'can still navigate on a phone. Known bug: the side menu and header are hidden below 900 px',
    async ({ page }) => {
      await signIn(page);

      await expect(page.getByRole('button', { name: 'SSIDs' })).toBeVisible({
        timeout: 3000,
      });
    },
  );
});
