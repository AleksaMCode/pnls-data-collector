// Integration tests of the SSID page: server-side search, sorting and paging, the map, and the CSV export.
import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../support/renderApp';
import { failRoute, requestsTo } from '../support/statsApi';
import { useViewerTimezone } from '../support/timezone';

function grid() {
  return screen.getByRole('grid');
}

/** The SSIDs on the current page of the table, in order. */
function ssidColumn() {
  return within(grid())
    .queryAllByRole('gridcell')
    .filter((cell) => cell.dataset.field === 'ssid')
    .map((cell) => cell.textContent);
}

function rowOf(ssid) {
  return within(grid())
    .getByRole('gridcell', { name: ssid })
    .closest('[role="row"]');
}

function cellOf(ssid, field) {
  return [...rowOf(ssid).querySelectorAll('[role="gridcell"]')].find(
    (cell) => cell.dataset.field === field,
  );
}

async function waitForFirstPage() {
  await waitFor(() => expect(ssidColumn()).toHaveLength(25));
}

function columnHeader(name) {
  return screen
    .getAllByRole('columnheader')
    .find((header) => header.textContent === name);
}

function lastSsidRequest() {
  return requestsTo('/stats/ssids').at(-1).params;
}

describe('SSID table', () => {
  it('asks for the 25 most recently seen SSIDs first', async () => {
    renderApp({ route: '/ssids' });
    await waitForFirstPage();

    expect(requestsTo('/stats/ssids')).toHaveLength(1);
    expect(lastSsidRequest()).toEqual({
      sort_by: 'last_seen',
      sort_order: 'desc',
      offset: '0',
      limit: '25',
    });
    expect(screen.getByText('1–25 of 30')).toBeInTheDocument();
  });

  it('shows the counts and Paris times of each SSID', async () => {
    renderApp({ route: '/ssids' });
    await waitForFirstPage();

    expect(cellOf('Network-14', 'seen_count')).toHaveTextContent(
      (140).toLocaleString(),
    );
    expect(cellOf('Network-14', 'first_seen')).toHaveTextContent(
      '14/05/2026, 08:00:00 AM',
    );
    expect(cellOf('Network-14', 'last_seen')).toHaveTextContent(
      '14/06/2026, 06:30:00 PM',
    );
  });

  it('formats times for the chosen language', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    // The language button has no accessible name, only its icon.
    await user.click(
      screen.getByTestId('LanguageRoundedIcon').closest('button'),
    );
    await user.click(await screen.findByRole('menuitem', { name: 'German' }));

    await waitFor(() =>
      expect(cellOf('Network-14', 'last_seen')).toHaveTextContent(
        '14.6.2026, 18:30:00',
      ),
    );
  });

  it.fails(
    'shows Paris times to a viewer in another timezone. Known bug: the API times are read as local time',
    async () => {
      useViewerTimezone('Europe/London');
      renderApp({ route: '/ssids' });
      await waitForFirstPage();

      expect(cellOf('Network-14', 'last_seen')).toHaveTextContent(
        '14/06/2026, 06:30:00 PM',
      );
    },
  );

  it('searches on the server once typing stops, from the first page', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();
    await user.click(screen.getByRole('button', { name: 'Go to next page' }));
    await waitFor(() => expect(lastSsidRequest().offset).toBe('25'));

    await user.type(
      screen.getByPlaceholderText('Search SSID...'),
      '  network-2  ',
    );

    await waitFor(() =>
      expect(ssidColumn()).toEqual(
        expect.arrayContaining(['Network-20', 'Network-29']),
      ),
    );
    const searches = requestsTo('/stats/ssids').filter((r) => r.params.search);
    // One request for the whole typed term, trimmed, and never one per keystroke.
    expect(new Set(searches.map((r) => r.params.search))).toEqual(
      new Set(['network-2']),
    );
    expect(lastSsidRequest()).toMatchObject({
      search: 'network-2',
      offset: '0',
    });
  });

  it('sorts on the server by the clicked column', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    await user.click(columnHeader('Seen count'));
    await waitFor(() =>
      expect(lastSsidRequest()).toMatchObject({
        sort_by: 'seen_count',
        sort_order: 'asc',
      }),
    );
    await waitFor(() => expect(ssidColumn()[0]).toBe('Network-01'));

    await user.click(columnHeader('Seen count'));
    await waitFor(() =>
      expect(lastSsidRequest()).toMatchObject({
        sort_by: 'seen_count',
        sort_order: 'desc',
      }),
    );
    await waitFor(() => expect(ssidColumn()[0]).toBe('Network-30'));
  });

  it('shows the SSIDs with a geolocation first on the first click of that column', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    await user.click(columnHeader('Geolocation'));

    await waitFor(() =>
      expect(lastSsidRequest()).toMatchObject({
        sort_by: 'has_geo',
        sort_order: 'desc',
      }),
    );
  });

  it('pages through the results on the server', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    await user.click(screen.getByRole('button', { name: 'Go to next page' }));

    await waitFor(() => expect(ssidColumn()).toHaveLength(5));
    expect(lastSsidRequest()).toMatchObject({ offset: '25', limit: '25' });
    expect(screen.getByText('26–30 of 30')).toBeInTheDocument();
  });

  it('shows an empty table when the API fails', async () => {
    failRoute('/stats/ssids');
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    renderApp({ route: '/ssids' });

    await waitFor(() => expect(requestsTo('/stats/ssids')).toHaveLength(2), {
      timeout: 5000,
    });
    await waitFor(() =>
      expect(consoleError).toHaveBeenCalledWith(
        'Failed to fetch SSID stats:',
        expect.any(Error),
      ),
    );
    expect(ssidColumn()).toEqual([]);
  });
});

describe('SSID map', () => {
  it('asks the viewer to pick an SSID', async () => {
    renderApp({ route: '/ssids' });
    await waitForFirstPage();

    expect(
      screen.getByText(
        'Select an SSID in the table to show its known locations on the map.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryAllByTestId('map-marker')).toHaveLength(0);
  });

  it('pins the locations of the selected SSID', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    await user.click(cellOf('Network-12', 'ssid'));

    expect(
      screen.getByText(
        'Showing 2 location(s) for "Network-12". Locations are approximate (about 1 km).',
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId('map-marker')).toHaveLength(2);
  });

  it('says so when the selected SSID has no geolocation', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    await user.click(cellOf('Network-13', 'ssid'));

    expect(
      screen.getByText('No geolocation is available for "Network-13".'),
    ).toBeInTheDocument();
    expect(screen.queryAllByTestId('map-marker')).toHaveLength(0);
  });

  it('drops the selection when the page changes', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();
    await user.click(cellOf('Network-12', 'ssid'));

    await user.click(screen.getByRole('button', { name: 'Go to next page' }));

    await waitFor(() =>
      expect(
        screen.getByText(
          'Select an SSID in the table to show its known locations on the map.',
        ),
      ).toBeInTheDocument(),
    );
    expect(screen.queryAllByTestId('map-marker')).toHaveLength(0);
  });
});

describe('CSV export', () => {
  let downloads;

  beforeEach(() => {
    downloads = [];
    URL.createObjectURL = vi.fn(() => 'blob:ssid-export');
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(
      function click() {
        downloads.push({ href: this.href, download: this.download });
      },
    );
  });

  afterEach(() => {
    delete URL.createObjectURL;
    delete URL.revokeObjectURL;
  });

  it('downloads the SSIDs with the current search and order', async () => {
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();
    await user.type(screen.getByPlaceholderText('Search SSID...'), 'network-1');
    await waitFor(() => expect(lastSsidRequest().search).toBe('network-1'));

    await user.click(screen.getByRole('button', { name: 'Download CSV' }));

    expect(
      await screen.findByText('SSID CSV downloaded successfully.'),
    ).toBeInTheDocument();
    expect(requestsTo('/stats/ssids/export').at(-1).params).toEqual({
      search: 'network-1',
      sort_by: 'last_seen',
      sort_order: 'desc',
    });
    expect(downloads).toEqual([
      { href: 'blob:ssid-export', download: 'ssid_stats_2026-06-15.csv' },
    ]);
    const blob = URL.createObjectURL.mock.calls[0][0];
    const csv = await blob.text();
    expect(csv.split('\n')[0]).toBe('ssid,seen_count,first_seen,last_seen');
    expect(csv).toContain('Network-10,100,');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:ssid-export');
    expect(screen.getByRole('button', { name: 'Download CSV' })).toBeEnabled();
  });

  it('tells the viewer when the download fails', async () => {
    failRoute('/stats/ssids/export');
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { user } = renderApp({ route: '/ssids' });
    await waitForFirstPage();

    await user.click(screen.getByRole('button', { name: 'Download CSV' }));

    expect(
      await screen.findByText('Failed to download SSID CSV.'),
    ).toBeInTheDocument();
    expect(downloads).toEqual([]);
    expect(screen.getByRole('button', { name: 'Download CSV' })).toBeEnabled();
  });
});
