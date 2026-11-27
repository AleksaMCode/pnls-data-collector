// An in-memory stand-in for the parts of `@firebase/database` the dashboard uses.
//
// Like the real SDK, a `child_added` listener first gets the children that already exist (only the last
// N of them under `limitToLast(N)`), asynchronously, and then every child added later.

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

function snapshot(path, value) {
  const key = segments(path).at(-1) ?? null;
  return {
    key,
    exists: () => value !== null && value !== undefined,
    val: () => (value === undefined ? null : structuredClone(value)),
    size: sortedKeys(value).length,
    child: (childPath) =>
      snapshot(
        `${path}/${childPath}`,
        readPath(`${normalize(path)}/${childPath}`),
      ),
    forEach(callback) {
      for (const childKey of sortedKeys(value)) {
        if (
          callback(snapshot(`${path}/${childKey}`, value[childKey])) === true
        ) {
          return true;
        }
      }
      return false;
    },
  };
}

function notifyChildAdded(parentPath, childKey) {
  const parent = normalize(parentPath);
  const value = readPath(`${parent}/${childKey}`);
  for (const listener of [...listeners]) {
    if (listener.path === parent) {
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

export function child(parent, path) {
  return ref(null, `${parent.path}/${path}`);
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

  const listener = { path: target.path, callback, active: true };
  listeners.push(listener);

  // Existing children arrive asynchronously, as they do from the real SDK.
  const existing = sortedKeys(readPath(target.path));
  const initial = target.limit ? existing.slice(-target.limit) : existing;
  queueMicrotask(() => {
    for (const childKey of initial) {
      if (!listener.active) return;
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
