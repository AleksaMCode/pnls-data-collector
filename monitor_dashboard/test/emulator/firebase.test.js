// The dashboard's Firebase readers against the real Realtime Database emulator and the real SDK.
import { afterEach, describe, expect, inject, it, vi } from 'vitest';
import * as firebase from '../../src/firebase/firebase';
import { pushValue, setValue } from '../support/emulator';
import { deviceNode, parisDate, parisWallTime } from '../support/paris';

const host = inject('databaseEmulatorHost');
const unsubscribes = [];

afterEach(() => {
  while (unsubscribes.length) unsubscribes.pop()();
});

/** Gives the SDK's listeners time to get their first data from the emulator. */
function settle() {
  return new Promise((resolve) => setTimeout(resolve, 1000));
}

function today() {
  return parisDate(new Date());
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
    // A row written before the listeners get their first data is lost (see the start-up race
    // ticket), so the test waits for that first data before writing.
    await settle();

    await addProbe('RPI-2');
    await addProbe('RPI-3');
    await addProbe('RPI-1');

    await vi.waitFor(() => expect(counts.at(-1)).toBe(6), { timeout: 5000 });
    // The first event of each device that already had rows is skipped, so nothing is counted twice.
    expect(counts).toEqual([3, 4, 5, 6]);
  });

  it('counts nothing more after unsubscribing', async () => {
    const counts = [];
    const result = await firebase.subscribeToLiveProbeRequestCount(
      ['RPI-1'],
      (count) => counts.push(count),
    );
    await settle();
    await addProbe('RPI-1');
    await vi.waitFor(() => expect(counts).toEqual([0, 1]), { timeout: 5000 });

    result.unsubscribe();
    await addProbe('RPI-1');
    // Gives a late event time to arrive.
    await settle();

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

    await addProbe('RPI-2', 'Other device');
    await addProbe('RPI-1', 'Yesterday', '2000-01-01');
    await addProbe('RPI-1', 'Mine');

    await vi.waitFor(() => expect(ssids).toEqual(['Mine']), { timeout: 5000 });
  });
});
