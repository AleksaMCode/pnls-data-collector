import { apiDownload, apiGet } from './client';

// Lightweight unauthenticated health check used to warm up the API.
export function fetchStatsApiHealth(options = {}) {
  return apiGet('/health', undefined, { ...options, auth: false });
}

// Total unique/all-time counts.
export function fetchTotalStats() {
  return apiGet('/stats/total');
}

// Average daily counts across historical daily-import rows (excluding today).
export function fetchAverageDailyCounts() {
  return apiGet('/stats/average/daily-counts');
}

// Aggregated totals for the last 30 days (excluding today).
export function fetchLast30DaysTotals() {
  return apiGet('/stats/last-30-days');
}

// Last 30 days totals together with per-day series.
export function fetchLast30DaysTotalsWithSeries() {
  return apiGet('/stats/last-30-days/totals-with-series');
}

// Totals for the 30 days preceding the last 30 days (for trend comparison).
export function fetchPrevious30DaysTotals() {
  return apiGet('/stats/previous-30-days/totals');
}

// Per-device probe request series for the last N days.
export function fetchProbeRequestsPerDeviceLastNDays(nDays = 30) {
  return apiGet('/stats/probe-requests-per-device', { n_days: nDays });
}

// Monthly totals aggregated across all devices.
export function fetchMonthlyTotalsAllDevices() {
  return apiGet('/stats/monthly-totals');
}

// Full daily series across all devices (excluding today).
export function fetchAllDataSeries() {
  return apiGet('/stats/series');
}

// Full daily series for a single device (excluding today).
export function fetchDeviceDataSeries(deviceName) {
  return apiGet(`/stats/series/${encodeURIComponent(deviceName)}`);
}

// All-time totals and location metadata per device.
export function fetchTotalPerDeviceStats() {
  return apiGet('/stats/devices');
}

// Aggregated manufacturer statistics.
export function fetchManufacturersData() {
  return apiGet('/stats/manufacturers');
}

// Per-device manufacturer breakdown used by the Sankey diagram.
export function fetchSankeyData() {
  return apiGet('/stats/sankey');
}

// Paginated, sortable, searchable SSID statistics.
export function fetchSsidStats({
  search,
  sortBy = 'last_seen',
  sortOrder = 'desc',
  offset = 0,
  limit = 100,
} = {}) {
  return apiGet('/stats/ssids', {
    search,
    sort_by: sortBy,
    sort_order: sortOrder,
    offset,
    limit,
  });
}

// CSV export with the same search/sort filters as the SSID list.
export function downloadSsidStatsCsv({
  search,
  sortBy = 'last_seen',
  sortOrder = 'desc',
} = {}) {
  return apiDownload('/stats/ssids/export', {
    search,
    sort_by: sortBy,
    sort_order: sortOrder,
  });
}
