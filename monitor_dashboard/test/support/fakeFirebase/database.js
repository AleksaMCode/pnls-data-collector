// An in-memory stand-in for the parts of `@firebase/database` the dashboard uses.
//
// Like the real SDK, a `child_added` listener first gets the children that already exist (only the last
// N of them under `limitToLast(N)`), asynchronously, and then every child added later that enters the
// query result: under `limitToLast(N)`, only one that is among the last N keys.

let root = {};
let listeners = [];
let pushCounter = 0;
let onNextListen = null;

function normalize(path) {
  return String(path ?? '')
    .split('/')
    .filter(Boolean)
    .join('/');
}

function segments(path) {
  return normalize(path).split('/').filter(Boolean);
}

function readPath(path) {
  let node = root;
  for (const segment of segments(path)) {
    if (node == null || typeof node !== 'object') return null;
    node = node[segment];
  }
  return node === undefined ? null : node;
}

function writePath(path, value) {
  const parts = segments(path);
  if (parts.length === 0) {
    root = value ?? {};
    return;
  }
  let node = root;
  for (const segment of parts.slice(0, -1)) {
    if (node[segment] == null || typeof node[segment] !== 'object') {
      node[segment] = {};
    }
    node = node[segment];
  }
  const last = parts.at(-1);
  if (value === null || value === undefined) {
    delete node[last];
  } else {
    node[last] = structuredClone(value);
  }
}

function sortedKeys(value) {
  return value && typeof value === 'object' ? Object.keys(value).sort() : [];
}

/**
 * Like the SDK's snapshots, it keeps the data as it was when it was read: the value is copied once,
 * here, and every field and method uses that copy, so later writes don't show through.
 */
function snapshot(path, value) {
  const key = segments(path).at(-1) ?? null;
  const data =
    value === undefined || value === null ? null : structuredClone(value);
  return {
    key,
    exists: () => data !== null,
    // A copy again, so a caller that changes the result doesn't change the snapshot.
    val: () => structuredClone(data),
    size: sortedKeys(data).length,
    forEach(callback) {
      for (const childKey of sortedKeys(data)) {
        if (
          callback(snapshot(`${path}/${childKey}`, data[childKey])) === true
        ) {
          return true;
        }
      }
      return false;
    },
  };
}

/** The keys a query selects now: all the children, or the last `limit` of them in key order. */
function selectedKeys(path, limit) {
  const keys = sortedKeys(readPath(path));
  return limit ? keys.slice(-limit) : keys;
}

/**
 * Tells each listener at the parent about a new child, if it entered the listener's query result.
 * Under limitToLast, a child older than the ones selected stays out, as it does in the SDK.
 */
function notifyChildAdded(parentPath, childKey) {
  const parent = normalize(parentPath);
  const value = readPath(`${parent}/${childKey}`);
  for (const listener of [...listeners]) {
    if (listener.path !== parent) continue;
    const selected = selectedKeys(parent, listener.limit);
    const entered =
      !listener.results.has(childKey) && selected.includes(childKey);
    listener.results = new Set(selected);
    if (entered) {
      listener.callback(snapshot(`${parent}/${childKey}`, value));
    }
  }
}

// --- The SDK surface -------------------------------------------------------------------------------

export function getDatabase(app) {
  return { app, type: 'fake-database' };
}

export function connectDatabaseEmulator() {}

export function ref(_db, path = '') {
  const normalized = normalize(path);
  return { path: normalized, key: segments(normalized).at(-1) ?? null };
}

export function limitToLast(limit) {
  return { type: 'limitToLast', limit };
}

export function query(target, ...constraints) {
  const limit = constraints.find((c) => c.type === 'limitToLast')?.limit;
  return { path: target.path, key: target.key, limit };
}

export async function get(target) {
  return snapshot(target.path, readPath(target.path));
}

export function onChildAdded(target, callback) {
  if (onNextListen) {
    const hook = onNextListen;
    onNextListen = null;
    hook(target.path);
  }

  const initial = selectedKeys(target.path, target.limit);
  const listener = {
    path: target.path,
    limit: target.limit,
    callback,
    active: true,
    // The children in the query result, so that later children are only reported on entering it.
    results: new Set(initial),
  };
  listeners.push(listener);

  // Existing children arrive asynchronously, as they do from the real SDK.
  queueMicrotask(() => {
    for (const childKey of initial) {
      if (!listener.active) return;
      // Pushed out of a limitToLast result by a child added in the meantime.
      if (!listener.results.has(childKey)) continue;
      const value = readPath(`${target.path}/${childKey}`);
      callback(snapshot(`${target.path}/${childKey}`, value));
    }
  });

  return () => off(target, 'child_added', callback);
}

export function off(target, _eventType, callback) {
  listeners = listeners.filter((listener) => {
    const matches =
      listener.path === target.path &&
      (callback === undefined || listener.callback === callback);
    if (matches) listener.active = false;
    return !matches;
  });
}

// --- Test controls ---------------------------------------------------------------------------------

export const fakeDatabase = {
  reset() {
    root = {};
    listeners = [];
    pushCounter = 0;
    onNextListen = null;
  },
  /** Replaces the value at a path, as `set()` would. */
  set(path, value) {
    const existedBefore = readPath(path) !== null;
    writePath(path, value);
    const parts = segments(path);
    if (!existedBefore && value != null && parts.length > 0) {
      notifyChildAdded(parts.slice(0, -1).join('/'), parts.at(-1));
    }
  },
  /** Adds a child with an increasing key, as `push()` would, and returns the key. */
  push(path, value) {
    pushCounter += 1;
    const key = `-N${String(pushCounter).padStart(6, '0')}`;
    this.set(`${normalize(path)}/${key}`, value);
    return key;
  },
  read(path) {
    return readPath(path);
  },
  /** The paths with a `child_added` listener attached, one entry per listener. */
  listenedPaths() {
    return listeners.map((listener) => listener.path);
  },
  /** Runs `hook(path)` inside the next `onChildAdded` call, before the listener is attached. */
  beforeNextListen(hook) {
    onNextListen = hook;
  },
};
