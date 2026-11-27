// A fake stats API for MSW. The data mirrors the fixtures of the stats API's own tests
// (tests/integration/stats_api_db.py), so both sides agree on what the endpoints return.
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { tokenFor } from './fakeFirebase/auth';

export const API = 'http://stats-api.test';

/** "Today" in the fixtures, in Paris. The dashboard's clock is frozen on this day. */
export const TODAY = '2026-06-15';

function last30Series(lastThree) {
  return [...Array(27).fill(0), ...lastThree];
}

export const fixtures = {
  total: { macCount: 9, ssidCount: 5, probeRequestCount: 1159 },
  averageDaily: { macCount: 15, ssidCount: 12, probeRequestCount: 40 },
  last30: {
    totals: { macCount: 12, probeRequestCount: 60, ssidCount: 9 },
    series: {
      macCount: last30Series([5, 4, 3]),
      probeRequestCount: last30Series([30, 20, 10]),
      ssidCount: last30Series([4, 3, 2]),
    },
  },
  previous30: {
    totals: { macCount: 50, probeRequestCount: 100, ssidCount: 40 },
  },
  series: {
    macCount: [50, 5, 4, 3],
    probeRequestCount: [100, 30, 20, 10],
    ssidCount: [40, 4, 3, 2],
    dates: ['2026-05-10', '2026-06-12', '2026-06-13', '2026-06-14'],
    dayCounts: 4,
  },
  deviceSeries: {
    'RPI-1': {
      macCount: [0, 3, 3, 2],
      probeRequestCount: [0, 20, 15, 10],
      ssidCount: [0, 2, 2, 1],
      dates: ['2026-05-10', '2026-06-12', '2026-06-13', '2026-06-14'],
      dayCounts: 4,
    },
    'RPI-2': {
      macCount: [5, 2, 0, 1],
      probeRequestCount: [100, 10, 0, 5],
      ssidCount: [5, 2, 0, 1],
      dates: ['2026-05-10', '2026-06-12', '2026-06-13', '2026-06-14'],
      dayCounts: 4,
    },
    'RPI-3': {
      macCount: [0, 0, 0, 0],
      probeRequestCount: [0, 0, 0, 0],
      ssidCount: [0, 0, 0, 0],
      dates: ['2026-05-10', '2026-06-12', '2026-06-13', '2026-06-14'],
      dayCounts: 4,
    },
  },
  // RPI-2 has no row on June 13 (see the stats API's per-device alignment ticket).
  probeRequestsPerDevice: { 'RPI-1': [20, 15, 10], 'RPI-2': [100, 10, 5] },
  // Totals include today's row, as the stats API's do.
  devices: {
    'RPI-1': {
      mac: 17,
      probe_requests: 1044,
      ssid: 14,
      location: 'Users Office (61/R-202)',
      coordinates: '46.23,6.04',
    },
    'RPI-2': {
      mac: 8,
      probe_requests: 115,
      ssid: 8,
      location: 'CERN Community Support Centre (62/R-001)',
      coordinates: null,
    },
    'RPI-3': {
      mac: 0,
      probe_requests: 0,
      ssid: 0,
      location: "Stefan's office (31/R-009)",
      coordinates: '46.23,6.05',
    },
  },
  monthlyTotals: {
    '2026-05': { probe_requests: 100, ssid: 5, mac: 5 },
    '2026-06': { probe_requests: 1059, ssid: 17, mac: 20 },
  },
  manufacturers: [
    { company: 'Apple, Inc.', country: 'USA', count: 5, percentage: 55.5556 },
    {
      company: 'Raspberry Pi Foundation',
      country: 'GBR',
      count: 3,
      percentage: 33.3333,
    },
    { company: 'Acme', country: null, count: 1, percentage: 11.1111 },
  ],
  sankey: {
    'RPI-1': {
      'Apple, Inc.': { country: 'United States' },
      Samsung: { country: 'South Korea' },
    },
    'RPI-2': { 'Raspberry Pi Foundation': { country: 'United Kingdom' } },
  },
  ssids: buildSsids(),
};

// 30 SSIDs, more than one page of 25. Times are Paris wall time with no offset, as the API sends them.
function buildSsids() {
  const items = [];
  for (let i = 1; i <= 30; i++) {
    const day = String(((i - 1) % 28) + 1).padStart(2, '0');
    items.push({
      ssid: `Network-${String(i).padStart(2, '0')}`,
      seen_count: i * 10,
      first_seen: `2026-05-${day}T08:00:00`,
      last_seen: `2026-06-${String(Math.min(i, 14)).padStart(2, '0')}T18:30:00`,
      has_geo: i % 3 === 0,
      geo:
        i % 3 === 0
          ? [
              { lat: 46.2044, lon: 6.1432, cc: 'CH' },
              { lat: 48.8566, lon: 2.3522, cc: 'FR' },
            ]
          : null,
    });
  }
  return items;
}

/** A tiny GeoJSON world for the manufacturer map: two square "countries". */
export const worldGeography = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'USA',
      properties: { name: 'United States', ISO_A3: 'USA' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-100, 30],
            [-90, 30],
            [-90, 40],
            [-100, 40],
            [-100, 30],
          ],
        ],
      },
    },
    {
      type: 'Feature',
      id: 'FRA',
      properties: { name: 'France', ISO_A3: 'FRA' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [0, 44],
            [5, 44],
            [5, 49],
            [0, 49],
            [0, 44],
          ],
        ],
      },
    },
  ],
};

// --- Request log -----------------------------------------------------------------------------------

/** Every request the fake API answered, oldest first. */
export const requests = [];

/** The logged requests to a path, e.g. requestsTo('/stats/ssids'). */
export function requestsTo(path) {
  return requests.filter((request) => request.path === path);
}

const allowedTokens = new Set();

/** Lets the API accept a user's ID token, as the real one accepts any token Firebase issued. */
export function allowUser(email) {
  allowedTokens.add(`Bearer ${tokenFor(email)}`);
}

export function resetStatsApi() {
  requests.length = 0;
  allowedTokens.clear();
}

function authorized(handler) {
  return async (info) => {
    const url = new URL(info.request.url);
    const authorization = info.request.headers.get('authorization');
    requests.push({
      path: url.pathname,
      params: Object.fromEntries(url.searchParams),
      authorization,
    });
    if (!allowedTokens.has(authorization)) {
      return HttpResponse.json(
        { detail: 'Invalid or expired Firebase token.' },
        { status: 401 },
      );
    }
    return handler(info, url);
  };
}

function ssidPage(url) {
  const search = (url.searchParams.get('search') ?? '').toLowerCase();
  const sortBy = url.searchParams.get('sort_by') ?? 'last_seen';
  const sortOrder = url.searchParams.get('sort_order') ?? 'desc';
  const offset = Number(url.searchParams.get('offset') ?? 0);
  const limit = Number(url.searchParams.get('limit') ?? 100);

  const matching = fixtures.ssids
    .filter((item) => item.ssid.toLowerCase().includes(search))
    .sort((a, b) => {
      const order = a[sortBy] < b[sortBy] ? -1 : a[sortBy] > b[sortBy] ? 1 : 0;
      // Ties are broken by SSID, as the API does.
      const tie = a.ssid.localeCompare(b.ssid);
      return (sortOrder === 'asc' ? order : -order) || tie;
    });

  return {
    items: matching.slice(offset, offset + limit),
    pagination: { total: matching.length, offset, limit },
  };
}

export const handlers = [
  http.get(`${API}/health`, ({ request }) => {
    requests.push({
      path: '/health',
      params: {},
      authorization: request.headers.get('authorization'),
    });
    return HttpResponse.json({ status: 'ok' });
  }),
  http.get(
    `${API}/stats/total`,
    authorized(() => HttpResponse.json(fixtures.total)),
  ),
  http.get(
    `${API}/stats/average/daily-counts`,
    authorized(() => HttpResponse.json(fixtures.averageDaily)),
  ),
  http.get(
    `${API}/stats/last-30-days/totals-with-series`,
    authorized(() => HttpResponse.json(fixtures.last30)),
  ),
  http.get(
    `${API}/stats/previous-30-days/totals`,
    authorized(() => HttpResponse.json(fixtures.previous30)),
  ),
  http.get(
    `${API}/stats/probe-requests-per-device`,
    authorized(() => HttpResponse.json(fixtures.probeRequestsPerDevice)),
  ),
  http.get(
    `${API}/stats/monthly-totals`,
    authorized(() => HttpResponse.json(fixtures.monthlyTotals)),
  ),
  http.get(
    `${API}/stats/series`,
    authorized(() => HttpResponse.json(fixtures.series)),
  ),
  http.get(
    `${API}/stats/series/:device`,
    authorized(({ params }) => {
      const series = fixtures.deviceSeries[params.device];
      return series
        ? HttpResponse.json(series)
        : HttpResponse.json({ detail: 'Unknown device.' }, { status: 404 });
    }),
  ),
  http.get(
    `${API}/stats/devices`,
    authorized(() => HttpResponse.json(fixtures.devices)),
  ),
  http.get(
    `${API}/stats/manufacturers`,
    authorized(() => HttpResponse.json(fixtures.manufacturers)),
  ),
  http.get(
    `${API}/stats/sankey`,
    authorized(() => HttpResponse.json(fixtures.sankey)),
  ),
  http.get(
    `${API}/stats/ssids`,
    authorized((_info, url) => HttpResponse.json(ssidPage(url))),
  ),
  http.get(
    `${API}/stats/ssids/export`,
    authorized((_info, url) => {
      const { items } = ssidPage(
        new URL(`${url.toString()}&offset=0&limit=1000`),
      );
      const csv = [
        'ssid,seen_count,first_seen,last_seen',
        ...items.map(
          (item) =>
            `${item.ssid},${item.seen_count},${item.first_seen},${item.last_seen}`,
        ),
      ].join('\n');
      return new HttpResponse(csv, {
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': `attachment; filename="ssid_stats_${TODAY}.csv"`,
        },
      });
    }),
  ),
  http.get('*/world-countries.json', () => HttpResponse.json(worldGeography)),
];

/** Answers a path with an error, for the rest of the test. */
export function failRoute(path, status = 500) {
  server.use(
    http.get(
      `${API}${path}`,
      authorized(() =>
        HttpResponse.json({ detail: 'Internal Server Error' }, { status }),
      ),
    ),
  );
}

const heldRoutes = new Set();

/** Keeps every request to a path pending until `release()` is called, or the test ends. */
export function holdRoute(path) {
  let release;
  const released = new Promise((resolve) => {
    release = resolve;
  });
  heldRoutes.add(release);
  server.use(
    http.get(`${API}${path}`, async () => {
      await released;
      // Falls through to the default handler, which logs and answers the request.
      return undefined;
    }),
  );
  return () => release();
}

export const server = setupServer(...handlers);

const pendingRequests = new Set();
server.events.on('request:start', ({ requestId }) =>
  pendingRequests.add(requestId),
);
server.events.on('request:end', ({ requestId }) =>
  pendingRequests.delete(requestId),
);

const nextTask = () => new Promise((resolve) => setTimeout(resolve, 10));

/**
 * Answers the held requests, then resolves once every request to the fake stats API has been
 * answered and the app has read the answers. The app's stats client shares a pending request
 * with any identical one made before it's answered, so one left pending at the end of a test
 * would answer the next test's request, or be logged in its requests.
 */
export async function settleStatsApi({ timeout = 5000 } = {}) {
  heldRoutes.forEach((release) => release());
  heldRoutes.clear();
  // Date is frozen in the integration tests, so the deadline uses performance.now().
  const deadline = performance.now() + timeout;
  // A request waiting for its ID token reaches MSW a moment later, so the requests must stay
  // answered over two checks in a row.
  let quietChecks = 0;
  while (quietChecks < 2) {
    await nextTask();
    quietChecks = pendingRequests.size ? 0 : quietChecks + 1;
    if (performance.now() > deadline) {
      throw new Error(
        `${pendingRequests.size} stats API request(s) still pending after the test`,
      );
    }
  }
}
