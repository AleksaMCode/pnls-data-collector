// Integration tests of the home page: the stat cards, charts, device grid, live count and lazy sections.
import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { fakeDatabase } from '../support/fakeFirebase/database';
import { deviceNode, parisInstant, parisWallTime } from '../support/paris';
import { renderApp } from '../support/renderApp';
import {
  API,
  failRoute,
  fixtures,
  holdRoute,
  requestsTo,
  server,
  TODAY,
} from '../support/statsApi';

const n = (value) => value.toLocaleString();

/** The stat card with a title and interval caption, e.g. ('SSIDs', 'Last 30 days'). */
function statCard(title, interval) {
  const cards = screen
    .getAllByText(interval)
    .map((caption) => caption.closest('.MuiCard-root'))
    .filter((card) => within(card).queryByText(title, { selector: 'h2' }));
  expect(cards).toHaveLength(1);
  return cards[0];
}

async function waitForStats() {
  await waitFor(() =>
    expect(
      within(statCard('Probe Requests', 'Total')).getByText(
        n(fixtures.total.probeRequestCount),
      ),
    ).toBeInTheDocument(),
  );
}

/** The device grid row of a device. */
function deviceRow(device) {
  const grid = screen.getAllByRole('grid')[0];
  const cell = within(grid).getByRole('gridcell', { name: device });
  return cell.closest('[role="row"]');
}

function writeHeartbeat(device, wallTime) {
  fakeDatabase.set(`${deviceNode(device, TODAY)}/status/timestamp`, wallTime);
}

describe('stat cards', () => {
  it('show the last 30 days with their trend over the 30 days before', async () => {
    renderApp();
    await waitForStats();

    const probes = statCard('Probe Requests', 'Last 30 days');
    expect(within(probes).getByText('60')).toBeInTheDocument();
    expect(within(probes).getByText('-40.0%')).toBeInTheDocument();
    const ssids = statCard('SSIDs', 'Last 30 days');
    expect(within(ssids).getByText('9')).toBeInTheDocument();
    expect(within(ssids).getByText('-77.5%')).toBeInTheDocument();
    const macs = statCard('MAC addresses', 'Last 30 days');
    expect(within(macs).getByText('12')).toBeInTheDocument();
    expect(within(macs).getByText('-76.0%')).toBeInTheDocument();
  });

  it('show the all-time totals and daily averages', async () => {
    renderApp();
    await waitForStats();

    expect(
      within(statCard('SSIDs', 'Total (unique)')).getByText('5'),
    ).toBeInTheDocument();
    expect(
      within(statCard('MAC addresses', 'Total (unique)')).getByText('9'),
    ).toBeInTheDocument();
    expect(
      within(statCard('Probe Requests', 'Average / day')).getByText('40'),
    ).toBeInTheDocument();
    expect(
      within(statCard('SSIDs', 'Average / day')).getByText('12'),
    ).toBeInTheDocument();
    expect(
      within(statCard('MAC addresses', 'Average / day')).getByText('15'),
    ).toBeInTheDocument();
  });

  it('fetch each endpoint once, even though several components share it', async () => {
    renderApp();
    await waitForStats();
    await waitFor(() => expect(requestsTo('/stats/devices')).toHaveLength(1));

    for (const path of [
      '/stats/total',
      '/stats/series',
      '/stats/average/daily-counts',
      '/stats/last-30-days/totals-with-series',
      '/stats/previous-30-days/totals',
      '/stats/probe-requests-per-device',
      '/stats/monthly-totals',
      '/stats/devices',
    ]) {
      expect(requestsTo(path), path).toHaveLength(1);
    }
    expect(requestsTo('/stats/probe-requests-per-device')[0].params).toEqual({
      n_days: '30',
    });
  });

  it('show spinners on the total and average cards while loading', async () => {
    const release = holdRoute('/stats/total');
    renderApp();

    await waitFor(() =>
      expect(
        within(statCard('Probe Requests', 'Total')).getByRole('progressbar'),
      ).toBeInTheDocument(),
    );
    expect(
      within(statCard('SSIDs', 'Average / day')).getByRole('progressbar'),
    ).toBeInTheDocument();

    release();
    await waitForStats();
  });

  it.fails(
    'show spinners on the last-30-days cards while loading. Known bug: they show 0 and a made-up sparkline',
    async () => {
      const release = holdRoute('/stats/last-30-days/totals-with-series');
      renderApp();
      await waitForStats();

      try {
        expect(
          within(statCard('Probe Requests', 'Last 30 days')).getByRole(
            'progressbar',
          ),
        ).toBeInTheDocument();
      } finally {
        release();
      }
    },
  );

  it.fails(
    'tell the viewer when the stats API fails. Known bug: the cards silently show zeros',
    async () => {
      failRoute('/stats/total');
      renderApp();

      // The production query settings retry once.
      await waitFor(() => expect(requestsTo('/stats/total')).toHaveLength(2), {
        timeout: 4000,
      });
      expect(await screen.findByRole('alert')).toBeInTheDocument();
    },
  );
});

describe('charts', () => {
  it('sum the cumulative probe requests per device', async () => {
    renderApp();

    // RPI-1: 20 + 15 + 10, RPI-2: 100 + 10 + 5.
    const chart = (
      await screen.findByText('Probe Requests per device (cumulative total)')
    ).closest('.MuiCard-root');
    await waitFor(() =>
      expect(within(chart).getByText('160')).toBeInTheDocument(),
    );
  });

  it('show the monthly totals', async () => {
    renderApp();

    expect(
      await screen.findByText('Captured information for the last 2 months'),
    ).toBeInTheDocument();
    const chart = screen
      .getByText('Captured information for the last 2 months')
      .closest('.MuiCard-root');
    expect(within(chart).getByText(n(1159))).toBeInTheDocument();
    expect(within(chart).getByText('may-26')).toBeInTheDocument();
    expect(within(chart).getByText('jun-26')).toBeInTheDocument();
  });

  it('name the devices in the comparison chart', async () => {
    renderApp();

    const chart = (
      await screen.findByText('Data comparison between capturing devices')
    ).closest('.MuiCard-root');
    await waitFor(() =>
      expect(within(chart).getAllByText(/^RPI-\d$/)).toHaveLength(3),
    );
  });
});

describe('device grid', () => {
  it("shows each device's totals and location", async () => {
    renderApp();

    await waitFor(() =>
      expect(within(deviceRow('RPI-1')).getByText(n(1044))).toBeInTheDocument(),
    );
    const rpi1 = deviceRow('RPI-1');
    expect(within(rpi1).getByText('14')).toBeInTheDocument();
    expect(within(rpi1).getByText('17')).toBeInTheDocument();
    expect(
      within(rpi1).getByText('Users Office (61/R-202)'),
    ).toBeInTheDocument();
    expect(
      within(deviceRow('RPI-2')).getByText(
        'CERN Community Support Centre (62/R-001)',
      ),
    ).toBeInTheDocument();
  });

  it('marks a device online when its heartbeat is recent', async () => {
    writeHeartbeat('RPI-1', `${TODAY} 09:58:00`);
    writeHeartbeat('RPI-2', `${TODAY} 08:00:00`);
    renderApp();

    await waitFor(() =>
      expect(
        within(deviceRow('RPI-1')).getByText('Online'),
      ).toBeInTheDocument(),
    );
    expect(within(deviceRow('RPI-1')).getByText('Working')).toBeInTheDocument();
    expect(within(deviceRow('RPI-2')).getByText('Offline')).toBeInTheDocument();
    expect(within(deviceRow('RPI-2')).getByText('Off')).toBeInTheDocument();
    expect(within(deviceRow('RPI-3')).getByText('Offline')).toBeInTheDocument();
  });

  it.fails(
    'notices a device that went offline. Known bug: the online status is cached for 6 hours',
    async () => {
      writeHeartbeat('RPI-1', `${TODAY} 09:58:00`);
      const { user } = renderApp();
      await waitFor(() =>
        expect(
          within(deviceRow('RPI-1')).getByText('Online'),
        ).toBeInTheDocument(),
      );

      // 15 minutes later RPI-1 has sent nothing; the viewer leaves the page and comes back.
      vi.setSystemTime(parisInstant(`${TODAY}T10:15:00`));
      await user.click(screen.getByRole('button', { name: 'SSIDs' }));
      await user.click(screen.getByRole('button', { name: 'Home' }));

      await waitFor(() =>
        expect(
          within(deviceRow('RPI-1')).getByText('Offline'),
        ).toBeInTheDocument(),
      );
    },
  );

  it.fails(
    'lists the devices the API returns. Known bug: the rows are the three hardcoded devices',
    async () => {
      server.use(
        http.get(`${API}/stats/devices`, () =>
          HttpResponse.json({
            ...fixtures.devices,
            'RPI-4': { mac: 1, probe_requests: 7, ssid: 1, location: 'Lab' },
          }),
        ),
      );
      renderApp();

      await waitFor(() => expect(deviceRow('RPI-4')).toBeInTheDocument());
    },
  );

  it.fails(
    'shows no made-up numbers while loading. Known bug: the hardcoded rows are shown until the data arrives',
    async () => {
      const release = holdRoute('/stats/probe-requests-per-device');
      renderApp();
      await waitFor(() => expect(deviceRow('RPI-1')).toBeInTheDocument());

      try {
        // The hardcoded probe request count of RPI-1.
        expect(within(deviceRow('RPI-1')).queryByText('212423')).toBeNull();
      } finally {
        release();
      }
    },
  );

  it('draws only the devices with coordinates and captures on the heat map', async () => {
    renderApp();

    const heatMap = (
      await screen.findByText('Device Heatmap (CERN Meyrin)')
    ).closest('.MuiAccordion-root');
    await waitFor(() =>
      expect(within(heatMap).getAllByTestId('map-marker')).toHaveLength(1),
    );
    expect(within(heatMap).getByTestId('map-tooltip')).toHaveTextContent(
      'RPI-1',
    );
  });

  it('loads the Sankey data only when its section is opened', async () => {
    const { user } = renderApp();
    await waitForStats();
    expect(requestsTo('/stats/sankey')).toHaveLength(0);

    await user.click(
      screen.getByText('Device to Manufacturer to Country (Sankey)'),
    );

    const diagram = await screen.findByRole('img', {
      name: 'Sankey diagram of device, company, and country',
    });
    expect(
      [...diagram.querySelectorAll('title')].map((t) => t.textContent),
    ).toContain('RPI-1 -> Samsung: 1');
    expect(requestsTo('/stats/sankey')).toHaveLength(1);
  });
});

describe('manufacturer section', () => {
  it('loads the manufacturers only when opened, most frequent first', async () => {
    const { user } = renderApp();
    await waitForStats();
    expect(requestsTo('/stats/manufacturers')).toHaveLength(0);

    await user.click(screen.getByText('Manufacturer data'));

    const section = screen
      .getByText('Manufacturer data')
      .closest('.MuiAccordion-root');
    await waitFor(() =>
      expect(within(section).getByText('Apple, Inc.')).toBeInTheDocument(),
    );
    const companies = within(section)
      .getAllByRole('gridcell')
      .filter((cell) => cell.dataset.field === 'company')
      .map((cell) => cell.textContent);
    expect(companies).toEqual([
      'Apple, Inc.',
      'Raspberry Pi Foundation',
      'Acme',
    ]);
    expect(within(section).getByText('55.5556%')).toBeInTheDocument();
    expect(requestsTo('/stats/manufacturers')).toHaveLength(1);
  });

  it('colors the countries on the world map by count once the section has opened', async () => {
    const { user, container } = renderApp();
    await waitForStats();

    await user.click(screen.getByText('Manufacturer data'));

    await waitFor(
      () =>
        expect(
          [...container.querySelectorAll('path title')].map(
            (t) => t.textContent,
          ),
        ).toEqual(['United States: 5', 'France: 0']),
      { timeout: 3000 },
    );
  });
});

describe('live view', () => {
  function addProbe(device) {
    fakeDatabase.push(`${deviceNode(device, TODAY)}/data`, {
      ssid: 'CERN-Guest',
      timestamp: parisWallTime(new Date()),
    });
  }

  function liveCard() {
    return statCard('Probe Requests', 'Live');
  }

  function liveSwitch() {
    // The tooltip's text names the switch.
    return screen.findByRole('switch', {
      name: 'Toggle to view live Probe Request data',
    });
  }

  it("counts today's probe requests and every new one while on", async () => {
    addProbe('RPI-1');
    addProbe('RPI-1');
    addProbe('RPI-2');
    const { user } = renderApp();
    await waitForStats();
    expect(within(liveCard()).getByText('0')).toBeInTheDocument();

    await user.click(await liveSwitch());
    await waitFor(() =>
      expect(within(liveCard()).getByText('3')).toBeInTheDocument(),
    );

    addProbe('RPI-2');
    await waitFor(() =>
      expect(within(liveCard()).getByText('4')).toBeInTheDocument(),
    );
    expect(within(liveCard()).getByText('+33.33%')).toBeInTheDocument();
    expect(fakeDatabase.listenedPaths()).toHaveLength(3);
  });

  it('stops listening when turned off or when the page changes', async () => {
    const { user } = renderApp();
    await waitForStats();

    await user.click(await liveSwitch());
    await waitFor(() => expect(fakeDatabase.listenedPaths()).toHaveLength(3));
    await user.click(await liveSwitch());
    expect(fakeDatabase.listenedPaths()).toEqual([]);

    await user.click(await liveSwitch());
    await waitFor(() => expect(fakeDatabase.listenedPaths()).toHaveLength(3));
    await user.click(screen.getByRole('button', { name: 'SSIDs' }));
    await waitFor(() => expect(fakeDatabase.listenedPaths()).toEqual([]));
  });
});
