// Unit tests that each stats API function calls the endpoint and parameters the API expects.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as StatsApi from './StatsApi';
import { apiDownload, apiGet } from './client';

vi.mock('./client', () => ({
  apiGet: vi.fn(async () => 'response'),
  apiDownload: vi.fn(async () => 'download'),
}));

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiDownload).mockClear();
});

describe('endpoints without parameters', () => {
  it.each([
    ['fetchTotalStats', '/stats/total'],
    ['fetchAverageDailyCounts', '/stats/average/daily-counts'],
    ['fetchLast30DaysTotals', '/stats/last-30-days'],
    [
      'fetchLast30DaysTotalsWithSeries',
      '/stats/last-30-days/totals-with-series',
    ],
    ['fetchPrevious30DaysTotals', '/stats/previous-30-days/totals'],
    ['fetchMonthlyTotalsAllDevices', '/stats/monthly-totals'],
    ['fetchAllDataSeries', '/stats/series'],
    ['fetchTotalPerDeviceStats', '/stats/devices'],
    ['fetchManufacturersData', '/stats/manufacturers'],
    ['fetchSankeyData', '/stats/sankey'],
  ])('%s calls %s with the token', async (name, path) => {
    await expect(StatsApi[name]()).resolves.toBe('response');

    expect(apiGet).toHaveBeenCalledWith(path);
  });
});

it('fetchStatsApiHealth calls /health without a token', async () => {
  await StatsApi.fetchStatsApiHealth({ cache: 'no-store' });

  expect(apiGet).toHaveBeenCalledWith('/health', undefined, {
    cache: 'no-store',
    auth: false,
  });
});

it('fetchStatsApiHealth never sends a token, whatever the options say', async () => {
  await StatsApi.fetchStatsApiHealth({ auth: true });

  expect(vi.mocked(apiGet).mock.calls[0][2].auth).toBe(false);
});

it('fetchProbeRequestsPerDeviceLastNDays asks for 30 days by default', async () => {
  await StatsApi.fetchProbeRequestsPerDeviceLastNDays();
  await StatsApi.fetchProbeRequestsPerDeviceLastNDays(7);

  expect(vi.mocked(apiGet).mock.calls).toEqual([
    ['/stats/probe-requests-per-device', { n_days: 30 }],
    ['/stats/probe-requests-per-device', { n_days: 7 }],
  ]);
});

it('fetchDeviceDataSeries puts the encoded device name in the path', async () => {
  await StatsApi.fetchDeviceDataSeries('RPI 1/a');

  expect(apiGet).toHaveBeenCalledWith('/stats/series/RPI%201%2Fa');
});

describe('fetchSsidStats', () => {
  it('asks for the newest 100 SSIDs by default', async () => {
    await StatsApi.fetchSsidStats();

    expect(apiGet).toHaveBeenCalledWith('/stats/ssids', {
      search: undefined,
      sort_by: 'last_seen',
      sort_order: 'desc',
      offset: 0,
      limit: 100,
    });
  });

  it('maps the options to the API parameters', async () => {
    await StatsApi.fetchSsidStats({
      search: 'cern',
      sortBy: 'seen_count',
      sortOrder: 'asc',
      offset: 25,
      limit: 25,
    });

    expect(apiGet).toHaveBeenCalledWith('/stats/ssids', {
      search: 'cern',
      sort_by: 'seen_count',
      sort_order: 'asc',
      offset: 25,
      limit: 25,
    });
  });
});

describe('downloadSsidStatsCsv', () => {
  it('downloads the export with the list filters and no paging', async () => {
    await expect(
      StatsApi.downloadSsidStatsCsv({
        search: 'cern',
        sortBy: 'ssid',
        sortOrder: 'asc',
      }),
    ).resolves.toBe('download');

    expect(apiDownload).toHaveBeenCalledWith('/stats/ssids/export', {
      search: 'cern',
      sort_by: 'ssid',
      sort_order: 'asc',
    });
  });

  it('uses the same default order as the list', async () => {
    await StatsApi.downloadSsidStatsCsv();

    expect(apiDownload).toHaveBeenCalledWith('/stats/ssids/export', {
      search: undefined,
      sort_by: 'last_seen',
      sort_order: 'desc',
    });
  });
});
