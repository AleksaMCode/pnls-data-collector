// Rows for the Supabase database the stats API reads in the end-to-end tests. They mirror the stats
// API's own test fixtures (tests/integration/stats_api_db.py), but are dated relative to the real
// "today", because the stats API runs unchanged and reads the clock itself.

/** "YYYY-MM-DD" in Paris, `days` days from today. */
export function parisDay(days = 0) {
  const date = new Date(Date.now() + days * 86_400_000);
  return date.toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' });
}

const sql = (value) =>
  value === null || value === undefined
    ? 'NULL'
    : typeof value === 'number'
      ? String(value)
      : `'${String(value).replaceAll("'", "''")}'`;

const json = (value) =>
  value === null ? 'NULL' : `${sql(JSON.stringify(value))}::jsonb`;

export const DEVICES = {
  'RPI-1': { location: 'Users Office (61/R-202)', coordinates: '46.23,6.04' },
  'RPI-2': {
    location: 'CERN Community Support Centre (62/R-001)',
    coordinates: null,
  },
  'RPI-3': {
    location: "Stefan's office (31/R-009)",
    coordinates: '46.23,6.05',
  },
};

/** The SSIDs, with how many days ago they were first and last seen. */
export const SSIDS = [
  {
    ssid: 'CERN',
    seen: 5,
    first: -14,
    last: -1,
    geo: [{ lat: 46.23, lon: 6.05, cc: 'CHE' }],
  },
  { ssid: 'CERN-Guest', seen: 1, first: -5, last: -5, geo: null },
  { ssid: 'eduroam', seen: 3, first: -13, last: -2, geo: null },
  { ssid: 'Home_5G', seen: 2, first: -10, last: -3, geo: null },
  {
    ssid: 'Cafe',
    seen: 1,
    first: -4,
    last: -4,
    geo: [{ lat: 48.86, lon: 2.35, cc: 'FRA' }],
  },
];

export function seedSql() {
  const daily = [
    // [days ago, probes, mac, ssid]
    [-36, 100, 50, 40],
    [-3, 30, 5, 4],
    [-2, 20, 4, 3],
    [-1, 10, 3, 2],
    [0, 999, 999, 999],
  ];
  const deviceDaily = [
    // [device, days ago, ssid, mac, probes]
    ['RPI-1', -3, 2, 3, 20],
    ['RPI-1', -2, 2, 3, 15],
    ['RPI-1', -1, 1, 2, 10],
    ['RPI-1', 0, 9, 9, 999],
    ['RPI-2', -36, 5, 5, 100],
    ['RPI-2', -3, 2, 2, 10],
    ['RPI-2', -1, 1, 1, 5],
  ];
  const statements = [];
  for (const [day, probes, mac, ssid] of daily) {
    for (const [table, count] of [
      ['daily_imports_probes', probes],
      ['daily_imports_mac', mac],
      ['daily_imports_ssid', ssid],
    ]) {
      statements.push(
        `INSERT INTO ${table} (date, count) VALUES (${sql(parisDay(day))}, ${count});`,
      );
    }
  }
  for (const [device, { location, coordinates }] of Object.entries(DEVICES)) {
    statements.push(
      `INSERT INTO devices (device, location, coordinates) VALUES (${sql(device)}, ${sql(location)}, ${sql(coordinates)});`,
    );
  }
  for (const [device, day, ssid, mac, probes] of deviceDaily) {
    statements.push(
      'INSERT INTO device_daily_imports (device_id, ssid, mac, probes, date) ' +
        `VALUES (${sql(device)}, ${ssid}, ${mac}, ${probes}, ${sql(parisDay(day))});`,
    );
  }
  for (const [company, country, alpha3, total, percentage] of [
    ['Apple, Inc.', 'United States', 'USA', 5, 55.5556],
    ['Raspberry Pi Foundation', 'United Kingdom', 'GBR', 3, 33.3333],
    ['Acme', null, null, 1, 11.1111],
  ]) {
    statements.push(
      'INSERT INTO manufacturer_stats (company, country, country_alpha3, total_occurrences, percentage) ' +
        `VALUES (${sql(company)}, ${sql(country)}, ${sql(alpha3)}, ${total}, ${percentage});`,
    );
  }
  statements.push(
    'INSERT INTO device_manufacturer_stats (device_id, manufacturer_data, date) VALUES ' +
      `('RPI-1', ${json([
        { company: 'Apple, Inc.', country: 'United States' },
        { company: 'Samsung', country: 'South Korea' },
      ])}, ${sql(parisDay(-1))});`,
  );
  for (const { ssid, seen, first, last, geo } of SSIDS) {
    statements.push(
      'INSERT INTO ssid_stats (ssid, seen_count, first_seen, last_seen, geo) ' +
        `VALUES (${sql(ssid)}, ${seen}, ${sql(`${parisDay(first)} 08:00`)}, ${sql(`${parisDay(last)} 18:30`)}, ${json(geo)});`,
    );
  }
  statements.push(
    'INSERT INTO unique_total_stats (totals, date) VALUES ' +
      `(${json({ probeRequestCount: 60, ssidCount: 5, macCount: 9 })}, ${sql(parisDay(-1))});`,
  );
  return statements.join('\n');
}

/** What the stats API answers for the rows above. */
export const EXPECTED = {
  totalProbeRequests: 1159,
  uniqueSsids: SSIDS.length,
  uniqueMacs: 9,
  last30Probes: 60,
  devices: Object.keys(DEVICES),
  rpi1ProbeRequests: 1044,
};
