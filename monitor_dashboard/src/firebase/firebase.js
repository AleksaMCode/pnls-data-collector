import { initializeApp } from 'firebase/app';
import { connectAuthEmulator, getAuth } from 'firebase/auth';
import {
  connectDatabaseEmulator,
  getDatabase,
  get,
  ref,
  onChildAdded,
  query,
  limitToLast,
  off,
} from '@firebase/database';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const ONLINE_WINDOW_MS = 11 * 60 * 1000; // 11 minutes

// Set only by the end-to-end tests, as "host:port", to use the Firebase emulators instead of the real
// project. Production builds leave them unset.
const authEmulatorHost = import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST;
const databaseEmulatorHost = import.meta.env
  .VITE_FIREBASE_DATABASE_EMULATOR_HOST;

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

if (authEmulatorHost) {
  connectAuthEmulator(auth, `http://${authEmulatorHost}`, {
    disableWarnings: true,
  });
}

let database;

function getFirebaseDb() {
  if (!database) {
    database = getDatabase(app);
    if (databaseEmulatorHost) {
      // The emulator must be connected before the first read, and only once.
      const separator = databaseEmulatorHost.lastIndexOf(':');
      connectDatabaseEmulator(
        database,
        databaseEmulatorHost.slice(0, separator),
        Number(databaseEmulatorHost.slice(separator + 1)),
      );
    }
  }
  return database;
}

export async function fetchDeviceOnlineStatus(devices = []) {
  const db = getFirebaseDb();

  // Today in Europe/Paris (YYYY-MM-DD)
  const today = new Date().toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });

  // Devices write their heartbeat under a per-day node, so right after
  // midnight today's node doesn't exist until the first heartbeat of the new
  // day. Fall back to yesterday's node; the freshness check below still
  // marks a device offline if that heartbeat is stale.
  const yesterdayDate = new Date(`${today}T00:00:00Z`);
  yesterdayDate.setUTCDate(yesterdayDate.getUTCDate() - 1);
  const yesterday = yesterdayDate.toISOString().slice(0, 10);

  // Heartbeats are Paris wall time with no UTC offset. Express "now" the same
  // way and read both as if they were UTC, so their difference is the elapsed
  // time and never depends on the viewer's timezone or DST rules. `sv-SE` is
  // used only because it formats as "YYYY-MM-DD HH:MM:SS", like the collector.
  const wallTimeMs = (value) =>
    Date.parse(`${String(value).slice(0, 23).replace(' ', 'T')}Z`);
  const now = wallTimeMs(
    new Date().toLocaleString('sv-SE', { timeZone: 'Europe/Paris' }),
  );
  const onlineStatus = {};

  if (!Array.isArray(devices) || devices.length === 0) {
    return onlineStatus;
  }

  await Promise.all(
    devices.map(async (device) => {
      let snapshot = await get(ref(db, `/${device}-${today}/status/timestamp`));

      if (!snapshot.exists()) {
        snapshot = await get(
          ref(db, `/${device}-${yesterday}/status/timestamp`),
        );
      }

      if (!snapshot.exists()) {
        onlineStatus[device] = false;
        return;
      }

      // Bounded on both sides so a future-dated heartbeat doesn't read as online.
      const age = now - wallTimeMs(snapshot.val());
      onlineStatus[device] = Math.abs(age) < ONLINE_WINDOW_MS;
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

export async function subscribeToLiveProbeRequestCount(devices, callback) {
  const db = getFirebaseDb();

  const today = new Date();
  const dateParts = today
    .toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' })
    .split('-');
  const [yyyy, mm, dd] = dateParts;
  const dateStr = `${yyyy}-${mm}-${dd}`;
  const listeners = [];

  const initialCountsByDevice = await Promise.all(
    devices.map(async (device) => {
      const path = `${device}-${dateStr}/data`;
      const dataRef = ref(db, path);
      const snapshot = await get(dataRef);
      return { device, count: snapshot.size };
    }),
  );

  const initialCount = initialCountsByDevice.reduce(
    (sum, entry) => sum + entry.count,
    0,
  );
  let totalCount = initialCount;

  // Emit the initial aggregated total once; avoid duplicate startup reads.
  callback(totalCount);
  const initialCountMap = new Map(
    initialCountsByDevice.map(({ device, count }) => [device, count]),
  );

  devices.forEach((device) => {
    const path = `${device}-${dateStr}/data`;
    const dataRef = ref(db, path);

    const futureRef = query(dataRef, limitToLast(1)); // only new children
    const hadExistingData = (initialCountMap.get(device) ?? 0) > 0;
    let ignoredInitialChild = false;
    const listener = () => {
      // Realtime DB emits one immediate child for limitToLast(1) when data exists.
      if (hadExistingData && !ignoredInitialChild) {
        ignoredInitialChild = true;
        return;
      }
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
