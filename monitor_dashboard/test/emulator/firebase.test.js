// The dashboard's Firebase readers against the real Realtime Database emulator and the real SDK.
import {
  limitToLast,
  onChildAdded,
  orderByKey,
  query,
  ref,
} from '@firebase/database';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  inject,
  it,
  vi,
} from 'vitest';
import * as firebase from '../../src/firebase/firebase';
import { pushValue, setValue } from '../support/emulator';
import {
  deviceNode,
  parisDate,
  parisInstant,
  parisWallTime,
} from '../support/paris';

const host = inject('databaseEmulatorHost');
const unsubscribes = [];
// A Paris daytime, away from midnight and the DST changes, so the dates and wall times the tests
// write don't depend on when they run.
const START = parisInstant('2026-06-15T10:00:00');

beforeEach(() => {
  // Only Date is faked, and it keeps advancing from START. The emulator traffic and the SDK's
  // listeners keep real timers. test/setup/emulator.js restores the real Date after each test.
  vi.useFakeTimers({ toFake: ['Date'], now: START, shouldAdvanceTime: true });
});

afterEach(() => {
  while (unsubscribes.length) unsubscribes.pop()();
});

function today() {
  return parisDate(new Date());
}

function rowsRef(device, date = today()) {
  return ref(firebase.getFirebaseDb(), `${deviceNode(device, date)}/data`);
}

/** The query subscribeToDeviceLiveData listens to, on today's node unless another date is given. */
function deviceLiveQuery(device, date = today()) {
  return query(rowsRef(device, date), limitToLast(1));
}

/** The query subscribeToLiveProbeRequestCount listens to for a device that had no rows yet. */
function newRowsQuery(device) {
  return query(rowsRef(device), orderByKey());
}

/**
 * Resolves once the SDK has delivered the row with `key` to listeners on `rowsQuery`. Events of
 * one query reach all its listeners together, so a listener that was still attached would have
 * been called by then.
 */
function rowDelivered(rowsQuery, key) {
  return new Promise((resolve) => {
    const stop = onChildAdded(rowsQuery, (snapshot) => {
      if (snapshot.key === key) {
        stop();
        resolve();
      }
    });
  });
}

function minutesAgo(minutes) {
  return parisWallTime(new Date(Date.now() - minutes * 60_000));
}

function addProbe(device, ssid = 'CERN-Guest', date = today()) {
  return pushValue(host, `${deviceNode(device, date)}/data`, {
    ssid,
    timestamp: parisWallTime(new Date()),
  });
}

it('runs at the pinned time, with a clock that still advances', async () => {
  expect(parisWallTime(new Date())).toMatch(/^2026-06-15 10:00:0/);
  const before = Date.now();
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(Date.now()).toBeGreaterThan(before);
});

it('reads through the emulator, not a real database', () => {
  const db = firebase.getFirebaseDb();

  expect(db._repoInternal.repoInfo_.host).toBe(host);
});

describe('fetchDeviceOnlineStatus', () => {
  it('reads the heartbeats the devices write', async () => {
    await setValue(host, `${deviceNode('RPI-1', today())}/status`, {
      timestamp: minutesAgo(2),
    });
    await setValue(host, `${deviceNode('RPI-2', today())}/status`, {
      timestamp: minutesAgo(30),
    });

    await expect(
      firebase.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2', 'RPI-3']),
    ).resolves.toEqual({ 'RPI-1': true, 'RPI-2': false, 'RPI-3': false });
  });

  // Known bug: heartbeats are compared as Paris wall times, so a DST change shifts their age by an
  // hour. At 03:01 on the spring-forward day, a heartbeat from 2 minutes ago reads 01:59, 62 minutes
  // earlier, and the device shows offline until its next heartbeat.
  it.fails(
    'keeps a device online across the spring-forward change',
    async () => {
      vi.setSystemTime(new Date('2026-03-29T01:01:00Z')); // 03:01 in Paris
      await setValue(host, `${deviceNode('RPI-1', today())}/status`, {
        timestamp: minutesAgo(2),
      });

      await expect(
        firebase.fetchDeviceOnlineStatus(['RPI-1']),
      ).resolves.toEqual({ 'RPI-1': true });
    },
  );
});

describe('subscribeToLiveProbeRequestCount', () => {
  it("counts today's rows once, then each new row, with the SDK's real events", async () => {
    await addProbe('RPI-1');
    await addProbe('RPI-1');
    await addProbe('RPI-2');
    const counts = [];

    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1', 'RPI-2', 'RPI-3'],
      (count) => counts.push(count),
    );
    unsubscribes.push(result.unsubscribe);
    expect(result.initialCount).toBe(3);

    // Written right away, likely before the listeners have their first data, which is when the
    // rows used to be lost.
    await addProbe('RPI-2');
    await addProbe('RPI-3');
    await addProbe('RPI-1');

    await vi.waitFor(() => expect(counts.at(-1)).toBe(6), { timeout: 5000 });
    // The rows read at the start aren't counted again.
    expect(counts).toEqual([3, 4, 5, 6]);
  });

  it('counts nothing more after unsubscribing', async () => {
    const counts = [];
    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1'],
      (count) => counts.push(count),
    );
    // So the listeners are detached even if a step below times out. Detaching twice does nothing.
    unsubscribes.push(result.unsubscribe);
    await addProbe('RPI-1');
    await vi.waitFor(() => expect(counts).toEqual([0, 1]), { timeout: 5000 });

    result.unsubscribe();
    const key = await addProbe('RPI-1');
    // Waits until the SDK has delivered the new row, which it would have done to the
    // dashboard's listener as well, had it still been attached.
    await rowDelivered(newRowsQuery('RPI-1'), key);

    expect(counts).toEqual([0, 1]);
  });
});

describe('subscribeToDeviceLiveData', () => {
  it('reports the latest row, then each new one, in order', async () => {
    await addProbe('RPI-1', 'Old');
    await addProbe('RPI-1', 'Latest');
    const ssids = [];

    unsubscribes.push(
      firebase.subscribeToDeviceLiveData('RPI-1', (row) =>
        ssids.push(row.ssid),
      ),
    );
    await vi.waitFor(() => expect(ssids).toEqual(['Latest']), {
      timeout: 5000,
    });
    await addProbe('RPI-1', 'First new');
    await addProbe('RPI-1', 'Second new');

    await vi.waitFor(
      () => expect(ssids).toEqual(['Latest', 'First new', 'Second new']),
      { timeout: 5000 },
    );
  });

  it('ignores rows of other devices and other days', async () => {
    const ssids = [];
    unsubscribes.push(
      firebase.subscribeToDeviceLiveData('RPI-1', (row) =>
        ssids.push(row.ssid),
      ),
    );

    const otherDevice = await addProbe('RPI-2', 'Other device');
    const otherDay = await addProbe('RPI-1', 'Other day', '2000-01-01');
    await addProbe('RPI-1', 'Mine');
    // Once the SDK has delivered the excluded rows on their own queries, a listener on the wrong
    // device or date would have been called too, so it can't add its row after the check passes.
    await rowDelivered(deviceLiveQuery('RPI-2'), otherDevice);
    await rowDelivered(deviceLiveQuery('RPI-1', '2000-01-01'), otherDay);

    await vi.waitFor(() => expect(ssids).toEqual(['Mine']), { timeout: 5000 });
  });
});
