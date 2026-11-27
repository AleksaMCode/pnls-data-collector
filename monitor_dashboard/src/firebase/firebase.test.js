// Unit tests of the Firebase readers the dashboard uses, against an in-memory database.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeDatabase } from '../../test/support/fakeFirebase/database';
import {
  deviceNode,
  parisInstant,
  parisWallTime,
} from '../../test/support/paris';
import { useViewerTimezone } from '../../test/support/timezone';
import * as firebase from './firebase';

vi.mock('firebase/app', () => import('../../test/support/fakeFirebase/app'));
vi.mock('firebase/auth', async () => ({
  ...(await import('../../test/support/fakeFirebase/auth')),
  connectAuthEmulator: vi.fn(),
}));
vi.mock('@firebase/database', async () => ({
  ...(await import('../../test/support/fakeFirebase/database')),
  connectDatabaseEmulator: vi.fn(),
}));

const TODAY = '2026-06-15';
const YESTERDAY = '2026-06-14';

/**
 * A fresh copy of the module, which reads the emulator variables again. Its database mocks are fresh
 * copies too, so tests that use it only check the calls it makes.
 */
async function loadFreshModule() {
  vi.resetModules();
  return import('./firebase');
}

function setNow(wallTime) {
  vi.setSystemTime(parisInstant(wallTime));
}

function writeHeartbeat(device, date, wallTime) {
  fakeDatabase.set(`${deviceNode(device, date)}/status/timestamp`, wallTime);
}

/** Lets the fake database deliver the listener events it queued. */
function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

beforeEach(() => {
  fakeDatabase.reset();
  setNow(`${TODAY}T10:00:00`);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('emulator connection', () => {
  it('connects to no emulator by default', async () => {
    const fresh = await loadFreshModule();
    const { connectAuthEmulator } = await import('firebase/auth');
    const { connectDatabaseEmulator } = await import('@firebase/database');

    await fresh.fetchDeviceOnlineStatus(['RPI-1']);

    expect(connectAuthEmulator).not.toHaveBeenCalled();
    expect(connectDatabaseEmulator).not.toHaveBeenCalled();
  });

  it('connects to the emulators the e2e tests give', async () => {
    vi.stubEnv('VITE_FIREBASE_AUTH_EMULATOR_HOST', '127.0.0.1:9099');
    vi.stubEnv('VITE_FIREBASE_DATABASE_EMULATOR_HOST', '127.0.0.1:9000');
    const fresh = await loadFreshModule();
    const { connectAuthEmulator } = await import('firebase/auth');
    const { connectDatabaseEmulator } = await import('@firebase/database');

    await fresh.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2']);
    await fresh.fetchDeviceOnlineStatus(['RPI-1']);

    expect(connectAuthEmulator).toHaveBeenCalledWith(
      fresh.auth,
      'http://127.0.0.1:9099',
      { disableWarnings: true },
    );
    // Connecting twice throws in the real SDK, so it happens once, before the first read.
    expect(connectDatabaseEmulator).toHaveBeenCalledTimes(1);
    expect(connectDatabaseEmulator).toHaveBeenCalledWith(
      fresh.getFirebaseDb(),
      '127.0.0.1',
      9000,
    );
  });

  it('keeps the host of an IPv6 emulator address whole', async () => {
    vi.stubEnv('VITE_FIREBASE_DATABASE_EMULATOR_HOST', '[::1]:9000');
    const fresh = await loadFreshModule();
    const { connectDatabaseEmulator } = await import('@firebase/database');

    fresh.getFirebaseDb();

    expect(connectDatabaseEmulator).toHaveBeenCalledWith(
      expect.anything(),
      '[::1]',
      9000,
    );
  });
});

describe('fetchDeviceOnlineStatus', () => {
  it('returns nothing for no devices', async () => {
    await expect(firebase.fetchDeviceOnlineStatus([])).resolves.toEqual({});
    await expect(firebase.fetchDeviceOnlineStatus()).resolves.toEqual({});
    await expect(firebase.fetchDeviceOnlineStatus('RPI-1')).resolves.toEqual(
      {},
    );
  });

  it('marks a device online when its heartbeat is less than 11 minutes old', async () => {
    writeHeartbeat('RPI-1', TODAY, `${TODAY} 09:50:30`);
    writeHeartbeat('RPI-2', TODAY, `${TODAY} 09:48:00`);

    await expect(
      firebase.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2']),
    ).resolves.toEqual({ 'RPI-1': true, 'RPI-2': false });
  });

  it('marks a device without a heartbeat offline', async () => {
    await expect(firebase.fetchDeviceOnlineStatus(['RPI-1'])).resolves.toEqual({
      'RPI-1': false,
    });
  });

  it('marks a heartbeat from the future offline', async () => {
    writeHeartbeat('RPI-1', TODAY, `${TODAY} 10:20:00`);
    writeHeartbeat('RPI-2', TODAY, `${TODAY} 10:05:00`);

    await expect(
      firebase.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2']),
    ).resolves.toEqual({ 'RPI-1': false, 'RPI-2': true });
  });

  it("reads yesterday's node just after midnight, before today's exists", async () => {
    setNow(`${TODAY}T00:04:00`);
    writeHeartbeat('RPI-1', YESTERDAY, `${YESTERDAY} 23:59:00`);
    writeHeartbeat('RPI-2', YESTERDAY, `${YESTERDAY} 18:00:00`);

    await expect(
      firebase.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2']),
    ).resolves.toEqual({ 'RPI-1': true, 'RPI-2': false });
  });

  it("prefers today's node over yesterday's", async () => {
    writeHeartbeat('RPI-1', TODAY, `${TODAY} 09:59:00`);
    writeHeartbeat('RPI-1', YESTERDAY, `${YESTERDAY} 10:00:00`);

    await expect(firebase.fetchDeviceOnlineStatus(['RPI-1'])).resolves.toEqual({
      'RPI-1': true,
    });
  });

  it('crosses month and year boundaries for yesterday', async () => {
    setNow('2027-01-01T00:02:00');
    writeHeartbeat('RPI-1', '2026-12-31', '2026-12-31 23:58:00');

    await expect(firebase.fetchDeviceOnlineStatus(['RPI-1'])).resolves.toEqual({
      'RPI-1': true,
    });
  });

  it('accepts heartbeats with milliseconds or an ISO "T"', async () => {
    writeHeartbeat('RPI-1', TODAY, `${TODAY} 09:58:00.123456`);
    writeHeartbeat('RPI-2', TODAY, `${TODAY}T09:58:00`);

    await expect(
      firebase.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2']),
    ).resolves.toEqual({ 'RPI-1': true, 'RPI-2': true });
  });

  it('gives the same answer to a viewer in another timezone', async () => {
    useViewerTimezone('America/New_York');
    writeHeartbeat('RPI-1', TODAY, `${TODAY} 09:55:00`);
    writeHeartbeat('RPI-2', TODAY, `${TODAY} 09:40:00`);

    await expect(
      firebase.fetchDeviceOnlineStatus(['RPI-1', 'RPI-2']),
    ).resolves.toEqual({ 'RPI-1': true, 'RPI-2': false });
  });

  it("uses Paris's date when the viewer's date is already tomorrow", async () => {
    useViewerTimezone('Pacific/Auckland');
    setNow(`${TODAY}T20:00:00`);
    writeHeartbeat('RPI-1', TODAY, `${TODAY} 19:58:00`);

    await expect(firebase.fetchDeviceOnlineStatus(['RPI-1'])).resolves.toEqual({
      'RPI-1': true,
    });
  });

  it('marks a device with an unreadable heartbeat offline', async () => {
    writeHeartbeat('RPI-1', TODAY, 'not a time');

    await expect(firebase.fetchDeviceOnlineStatus(['RPI-1'])).resolves.toEqual({
      'RPI-1': false,
    });
  });
});

describe('subscribeToLiveProbeRequestCount', () => {
  function addProbe(device, date = TODAY) {
    return fakeDatabase.push(`${deviceNode(device, date)}/data`, {
      ssid: 'CERN',
      timestamp: parisWallTime(new Date()),
    });
  }

  it("starts from the number of rows today's nodes already have", async () => {
    addProbe('RPI-1');
    addProbe('RPI-1');
    addProbe('RPI-2');
    addProbe('RPI-1', YESTERDAY);
    const callback = vi.fn();

    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1', 'RPI-2', 'RPI-3'],
      callback,
    );
    await flush();

    expect(result.initialCount).toBe(3);
    // The existing last row of each device is not counted a second time.
    expect(callback.mock.calls).toEqual([[3]]);
    result.unsubscribe();
  });

  it('counts every row added afterwards, on any device', async () => {
    addProbe('RPI-1');
    const callback = vi.fn();
    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1', 'RPI-2'],
      callback,
    );
    await flush();

    addProbe('RPI-1');
    addProbe('RPI-2');
    addProbe('RPI-2');

    expect(callback.mock.calls.map(([count]) => count)).toEqual([1, 2, 3, 4]);
    result.unsubscribe();
  });

  it('counts the first row of a device that had none yet', async () => {
    const callback = vi.fn();
    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1'],
      callback,
    );
    await flush();

    addProbe('RPI-1');

    expect(callback.mock.calls).toEqual([[0], [1]]);
    result.unsubscribe();
  });

  it("listens to the last row of each device's node for today in Paris", async () => {
    useViewerTimezone('America/Los_Angeles');
    setNow(`${TODAY}T08:00:00`); // Still June 14 in Los Angeles.
    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1', 'RPI-2'],
      vi.fn(),
    );

    expect(fakeDatabase.listenedPaths()).toEqual([
      `${deviceNode('RPI-1', TODAY)}/data`,
      `${deviceNode('RPI-2', TODAY)}/data`,
    ]);
    result.unsubscribe();
  });

  it('stops counting after unsubscribing', async () => {
    const callback = vi.fn();
    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1', 'RPI-2'],
      callback,
    );
    await flush();

    result.unsubscribe();
    addProbe('RPI-1');

    expect(fakeDatabase.listenedPaths()).toEqual([]);
    expect(callback.mock.calls).toEqual([[0]]);
  });

  it.fails(
    'keeps counting after Paris midnight. Known bug: the subscription stays on the day it started',
    async () => {
      setNow(`${TODAY}T23:59:00`);
      const callback = vi.fn();
      const result = await firebase.subscribeToLiveProbeRequestCount(
        ['RPI-1'],
        callback,
      );
      await flush();

      setNow('2026-06-16T00:01:00');
      addProbe('RPI-1', '2026-06-16');

      expect(callback).toHaveBeenLastCalledWith(1);
      result.unsubscribe();
    },
  );

  it.fails(
    'counts a row written while subscribing. Known bug: it is taken for the row already counted',
    async () => {
      addProbe('RPI-1');
      // The device writes between the initial read and the listener.
      fakeDatabase.beforeNextListen(() => addProbe('RPI-1'));
      const callback = vi.fn();

      const result = await firebase.subscribeToLiveProbeRequestCount(
        ['RPI-1'],
        callback,
      );
      await flush();

      expect(callback).toHaveBeenLastCalledWith(2);
      result.unsubscribe();
    },
  );
});

describe('subscribeToDeviceLiveData', () => {
  function addRow(row, date = TODAY) {
    fakeDatabase.push(`${deviceNode('RPI-1', date)}/data`, row);
  }

  it('reports the latest row and every row added afterwards', async () => {
    addRow({ ssid: 'Old', timestamp: `${TODAY} 09:00:00` });
    addRow({ ssid: 'Latest', timestamp: `${TODAY} 09:30:00` });
    const onRow = vi.fn();

    const unsubscribe = firebase.subscribeToDeviceLiveData('RPI-1', onRow);
    await flush();
    addRow({ ssid: 'New', timestamp: `${TODAY} 10:00:00`, mac: 'aa:bb' });

    expect(onRow.mock.calls).toEqual([
      [{ ssid: 'Latest', timestamp: `${TODAY} 09:30:00` }],
      [{ ssid: 'New', timestamp: `${TODAY} 10:00:00` }],
    ]);
    unsubscribe();
  });

  it('skips rows without an SSID or a timestamp', async () => {
    const onRow = vi.fn();
    const unsubscribe = firebase.subscribeToDeviceLiveData('RPI-1', onRow);
    await flush();

    addRow({ ssid: 'NoTime' });
    addRow({ timestamp: `${TODAY} 10:00:00` });
    addRow({ ssid: '', timestamp: `${TODAY} 10:00:00` });

    expect(onRow).not.toHaveBeenCalled();
    unsubscribe();
  });

  it('stops after unsubscribing', async () => {
    const onRow = vi.fn();
    const unsubscribe = firebase.subscribeToDeviceLiveData('RPI-1', onRow);
    await flush();

    unsubscribe();
    addRow({ ssid: 'Late', timestamp: `${TODAY} 10:00:00` });

    expect(onRow).not.toHaveBeenCalled();
  });

  it.fails(
    'keeps reporting rows after Paris midnight. Known bug: the subscription stays on the day it started',
    async () => {
      setNow(`${TODAY}T23:59:00`);
      const onRow = vi.fn();
      const unsubscribe = firebase.subscribeToDeviceLiveData('RPI-1', onRow);
      await flush();

      setNow('2026-06-16T00:01:00');
      addRow(
        { ssid: 'AfterMidnight', timestamp: '2026-06-16 00:01:00' },
        '2026-06-16',
      );

      expect(onRow).toHaveBeenCalledWith({
        ssid: 'AfterMidnight',
        timestamp: '2026-06-16 00:01:00',
      });
      unsubscribe();
    },
  );
});
