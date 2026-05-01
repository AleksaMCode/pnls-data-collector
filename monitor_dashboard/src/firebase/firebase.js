import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import {
  getDatabase,
  get,
  ref,
  onChildAdded,
  query,
  limitToLast,
  off,
  child,
} from '@firebase/database';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREABSE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREABASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const ONLINE_WINDOW_MS = 11 * 60 * 1000; // 11 minutes

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function getFirebaseDb() {
  return getDatabase(app);
}

function getLastNDates(n) {
  const dates = [];
  const now = new Date();

  for (let i = 0; i < n; i++) {
    const d = new Date(now);
    d.setDate(now.getDate() - i - 1);
    dates.push(d.toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' }));
  }

  return dates;
}

export async function fetchDeviceOnlineStatus() {
  const db = getFirebaseDb();

  // Today in Europe/Paris (YYYY-MM-DD)
  const today = new Date().toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });

  const now = Date.now();
  const onlineStatus = {};
  const devices = ['RPI-1', 'RPI-2', 'RPI-3'];

  await Promise.all(
    devices.map(async (device) => {
      const path = `/${device}-${today}/status/timestamp`;
      const snapshot = await get(ref(db, path));

      if (!snapshot.exists()) {
        onlineStatus[device] = false;
        return;
      }

      const timestamp = Date.parse(snapshot.val());
      onlineStatus[device] = now - timestamp < ONLINE_WINDOW_MS;
    }),
  );

  return onlineStatus;
}

export function subscribeToDeviceLiveData(deviceId, onRow) {
  const db = getFirebaseDb();

  const today = new Date().toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });

  const deviceRef = ref(db, `/${deviceId}-${today}/data`);

  const deviceQuery = query(deviceRef, limitToLast(1));

  const unsubscribe = onChildAdded(deviceQuery, (snapshot) => {
    const value = snapshot.val();
    if (!value) return;
    if (value.ssid && value.timestamp) {
      onRow({
        ssid: value.ssid,
        timestamp: value.timestamp,
      });
    }
  });

  return () => unsubscribe();
}

export async function fetchLast30DaysTotals() {
  const db = getFirebaseDb();
  const dates = getLastNDates(30);

  let totalMac = 0;
  let totalProbeRequests = 0;
  let totalSsid = 0;

  await Promise.all(
    dates.map(async (dateStr) => {
      const dayRef = ref(db, `stats/daily/${dateStr}`);
      const snapshot = await get(dayRef);

      if (!snapshot.exists()) return;

      snapshot.forEach((deviceSnap) => {
        const data = deviceSnap.val() || {};

        totalMac += data.mac ?? 0;
        totalProbeRequests += data.probe_requests ?? 0;
        totalSsid += data.ssid ?? 0;
      });
    }),
  );

  return {
    macCount: totalMac,
    probeRequestCount: totalProbeRequests,
    ssidCount: totalSsid,
  };
}

export async function fetchLast30DaysTotalsWithSeries() {
  const db = getFirebaseDb();
  const dates = getLastNDates(30);

  let totalMac = 0;
  let totalProbeRequests = 0;
  let totalSsid = 0;

  const macSeries = [];
  const probeSeries = [];
  const ssidSeries = [];

  await Promise.all(
    dates.map(async (dateStr) => {
      const dayRef = ref(db, `stats/daily/${dateStr}`);
      const snapshot = await get(dayRef);

      let dayMac = 0;
      let dayProbe = 0;
      let daySsid = 0;

      if (snapshot.exists()) {
        snapshot.forEach((deviceSnap) => {
          const data = deviceSnap.val() || {};

          dayMac += data.mac ?? 0;
          dayProbe += data.probe_requests ?? 0;
          daySsid += data.ssid ?? 0;
        });
      }

      // per-day arrays
      macSeries.push(dayMac);
      probeSeries.push(dayProbe);
      ssidSeries.push(daySsid);

      // running totals
      totalMac += dayMac;
      totalProbeRequests += dayProbe;
      totalSsid += daySsid;
    }),
  );

  return {
    totals: {
      macCount: totalMac,
      probeRequestCount: totalProbeRequests,
      ssidCount: totalSsid,
    },
    series: {
      macCount: macSeries.reverse(),
      probeRequestCount: probeSeries.reverse(),
      ssidCount: ssidSeries.reverse(),
    },
  };
}

export async function fetchProbeRequestsPerDeviceLastNDays(nDays = 30) {
  const db = getFirebaseDb();
  const dailyRef = ref(db, 'stats/daily');

  const snapshot = await get(dailyRef);
  if (!snapshot.exists()) return {};

  // Get date keys, sorted ascending
  const dateKeys = [];
  snapshot.forEach((dateSnap) => {
    dateKeys.push(dateSnap.key);
  });

  dateKeys.sort(); // YYYY-MM-DD sorts correctly

  const today = new Date().toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });

  const filteredDates = dateKeys.filter((d) => d !== today).slice(-nDays); // last N days only

  const seriesPerDevice = {};

  for (const date of filteredDates) {
    const daySnap = snapshot.child(date);

    daySnap.forEach((deviceSnap) => {
      const device = deviceSnap.key;
      const data = deviceSnap.val() || {};

      if (!seriesPerDevice[device]) {
        seriesPerDevice[device] = [];
      }

      seriesPerDevice[device].push(data.probe_requests ?? 0);
    });
  }

  return seriesPerDevice;
}

export async function fetchMonthlyTotalsAllDevices() {
  const db = getFirebaseDb();
  const dailyRef = ref(db, 'stats/daily');

  const snapshot = await get(dailyRef);
  if (!snapshot.exists()) return {};

  const monthlyTotals = {};

  snapshot.forEach((dateSnap) => {
    const dateKey = dateSnap.key; // e.g. "2024-03-14"
    if (!dateKey) return;

    // Extract YYYY-MM
    const monthKey = dateKey.slice(0, 7); // "2024-03"

    if (!monthlyTotals[monthKey]) {
      monthlyTotals[monthKey] = {
        probe_requests: 0,
        ssid: 0,
        mac: 0,
      };
    }

    // Sum across all devices for this day
    dateSnap.forEach((deviceSnap) => {
      const data = deviceSnap.val() || {};

      monthlyTotals[monthKey].probe_requests += data.probe_requests ?? 0;
      monthlyTotals[monthKey].ssid += data.ssid ?? 0;
      monthlyTotals[monthKey].mac += data.mac ?? 0;
    });
  });

  return monthlyTotals;
}

export async function fetchAllDataSeries() {
  const db = getFirebaseDb();

  const dailyRef = ref(db, 'stats/daily');
  const snapshot = await get(dailyRef);
  if (!snapshot.exists())
    return { macCount: [], probeRequestCount: [], ssidCount: [], dates: [] };

  const dateKeys = Object.keys(snapshot.val()).sort(); // oldest → newest
  const macSeries = [];
  const probeSeries = [];
  const ssidSeries = [];

  const today = new Date();
  const todayStr = today.toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });

  for (const dateStr of dateKeys) {
    // Skip today
    if (dateStr === todayStr) {
      continue;
    }
    const dayRef = child(dailyRef, dateStr);
    const daySnap = await get(dayRef);

    let dayMac = 0;
    let dayProbe = 0;
    let daySsid = 0;

    if (daySnap.exists()) {
      daySnap.forEach((deviceSnap) => {
        const data = deviceSnap.val() || {};
        dayMac += data.mac ?? 0;
        dayProbe += data.probe_requests ?? 0;
        daySsid += data.ssid ?? 0;
      });
    }

    macSeries.push(dayMac);
    probeSeries.push(dayProbe);
    ssidSeries.push(daySsid);
  }

  return {
    macCount: macSeries,
    probeRequestCount: probeSeries,
    ssidCount: ssidSeries,
    dayCounts: dateKeys.length, // optional, useful for chart x-axis
  };
}

export async function fetchDeviceDataSeries(deviceName) {
  const db = getFirebaseDb();

  const dailyRef = ref(db, 'stats/daily');
  const snapshot = await get(dailyRef);

  if (!snapshot.exists()) {
    return {
      macCount: [],
      probeRequestCount: [],
      ssidCount: [],
      dates: [],
    };
  }

  const dateKeys = Object.keys(snapshot.val()).sort(); // oldest → newest

  const macSeries = [];
  const probeSeries = [];
  const ssidSeries = [];
  let days = 0;

  const todayStr = new Date().toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });

  for (const dateStr of dateKeys) {
    // Skip today
    if (dateStr === todayStr) continue;

    const deviceRef = ref(db, `stats/daily/${dateStr}/${deviceName}`);
    const deviceSnap = await get(deviceRef);

    if (deviceSnap.exists()) {
      const data = deviceSnap.val() || {};

      macSeries.push(data.mac ?? 0);
      probeSeries.push(data.probe_requests ?? 0);
      ssidSeries.push(data.ssid ?? 0);
    } else {
      // Push zeros to keep chart aligned for missing data (data will not be missing!)
      macSeries.push(0);
      probeSeries.push(0);
      ssidSeries.push(0);
    }

    days += 1;
  }

  return {
    macCount: macSeries,
    probeRequestCount: probeSeries,
    ssidCount: ssidSeries,
    dayCounts: days,
  };
}

export async function fetchTotalPerDeviceStats() {
  const db = getFirebaseDb();
  const dailyRef = ref(db, 'stats/daily'); // all dates

  const snapshot = await get(dailyRef);
  if (!snapshot.exists()) return {};

  const totalsPerDevice = {};

  snapshot.forEach((dateSnap) => {
    dateSnap.forEach((deviceSnap) => {
      const deviceName = deviceSnap.key; // e.g., "RPI-1"
      const data = deviceSnap.val() || {};

      if (!totalsPerDevice[deviceName]) {
        totalsPerDevice[deviceName] = {
          mac: 0,
          probe_requests: 0,
          ssid: 0,
        };
      }

      totalsPerDevice[deviceName].mac += data.mac ?? 0;
      totalsPerDevice[deviceName].probe_requests += data.probe_requests ?? 0;
      totalsPerDevice[deviceName].ssid += data.ssid ?? 0;
    });
  });

  return totalsPerDevice;
}

export async function fetchPrevious30DaysTotals() {
  const db = getFirebaseDb();

  // get the 30 days before last 30 days
  const today = new Date();
  const dates = [];
  for (let i = 59; i >= 30; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i - 1);
    const dateStr = d.toISOString().slice(0, 10); // YYYY-MM-DD
    dates.push(dateStr);
  }

  let totalMac = 0;
  let totalProbeRequests = 0;
  let totalSsid = 0;

  await Promise.all(
    dates.map(async (dateStr) => {
      const dayRef = ref(db, `stats/daily/${dateStr}`);
      const snapshot = await get(dayRef);

      let dayMac = 0;
      let dayProbe = 0;
      let daySsid = 0;

      if (snapshot.exists()) {
        snapshot.forEach((deviceSnap) => {
          const data = deviceSnap.val() || {};

          dayMac += data.mac ?? 0;
          dayProbe += data.probe_requests ?? 0;
          daySsid += data.ssid ?? 0;
        });
      }

      totalMac += dayMac;
      totalProbeRequests += dayProbe;
      totalSsid += daySsid;
    }),
  );

  return {
    totals: {
      macCount: totalMac,
      probeRequestCount: totalProbeRequests,
      ssidCount: totalSsid,
    },
  };
}

export async function fetchTotalStats() {
  const db = getFirebaseDb();

  try {
    const snapshot = await get(ref(db, 'stats'));

    if (!snapshot.exists()) {
      return {
        macCount: 0,
        ssidCount: 0,
        probeRequestCount: 0,
      };
    }

    const stats = snapshot.val();

    return {
      macCount: stats.mac_count.count,
      ssidCount: stats.ssid_count.count,
      probeRequestCount: stats.total_count.count,
    };
  } catch (error) {
    console.error('Failed to fetch stats:', error);
    throw error;
  }
}

export async function fetchManufacturersData() {
  const db = getFirebaseDb();

  try {
    const snapshot = await get(ref(db, 'stats/manufacturers'));

    if (!snapshot.exists()) {
      return [];
    }

    const manufacturers = [];
    snapshot.forEach((companySnap) => {
      const companyData = companySnap.val() || {};
      manufacturers.push({
        company: companySnap.key ?? '',
        country: companyData.country ?? null,
        count: Number(companyData.count ?? 0),
        // Backward-compatible with older typo key.
        percentage: Number(
          companyData.percentage ?? companyData.percetage ?? 0,
        ),
      });
    });

    return manufacturers;
  } catch (error) {
    console.error('Failed to fetch manufacturers data:', error);
    throw error;
  }
}

export async function fetchSankeyData() {
  const db = getFirebaseDb();

  try {
    const snapshot = await get(ref(db, 'stats/sankey'));

    if (!snapshot.exists()) {
      return {};
    }

    const sankeyData = {};

    snapshot.forEach((deviceSnap) => {
      const deviceKey = deviceSnap.key ?? '';
      sankeyData[deviceKey] = {};

      deviceSnap.forEach((manufacturerSnap) => {
        const manufacturerData = manufacturerSnap.val() || {};
        sankeyData[deviceKey][manufacturerSnap.key ?? ''] = {
          country: manufacturerData.country ?? null,
        };
      });
    });

    return sankeyData;
  } catch (error) {
    console.error('Failed to fetch sankey data:', error);
    throw error;
  }
}

export async function subscribeToLiveProbeRequestCount(devices, callback) {
  const db = getFirebaseDb();

  const today = new Date();
  const dateParts = today
    .toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' })
    .split('-');
  const [yyyy, mm, dd] = dateParts;
  const dateStr = `${yyyy}-${mm}-${dd}`;
  let totalCount = 0;
  const listeners = [];

  const initialCounts = await Promise.all(
    devices.map(async (device) => {
      const path = `${device}-${dateStr}/data`;
      const dataRef = ref(db, path);
      const snapshot = await get(dataRef);
      return snapshot.size;
    }),
  );

  const initialCount = initialCounts.reduce((a, b) => a + b, 0);

  devices.forEach((device) => {
    const path = `${device}-${dateStr}/data`;
    const dataRef = ref(db, path);

    get(dataRef)
      .then((snapshot) => {
        totalCount += snapshot.size;
        callback(totalCount);
      })
      .catch((err) => {
        console.error(`Failed to fetch initial count for ${device}`, err);
      });

    const futureRef = query(dataRef, limitToLast(1)); // only new children
    const listener = () => {
      totalCount += 1;
      callback(totalCount);
    };
    onChildAdded(futureRef, listener);

    listeners.push({ ref: futureRef, listener });
  });
  // return unsubscribe function
  return {
    initialCount,
    unsubscribe: () => {
      listeners.forEach(({ ref, listener }) =>
        off(ref, 'child_added', listener),
      );
    },
  };
}

export { app, auth, getFirebaseDb };
