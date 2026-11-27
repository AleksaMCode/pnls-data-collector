// Writes to the Firebase Realtime Database emulator over its REST API, as the devices and the
// aggregator would. "owner" is the emulator's admin token, which bypasses the security rules.

/** The database the dashboard's config names (VITE_FIREBASE_DATABASE_URL in vitest.config.js). */
export const DATABASE_NAMESPACE = 'demo-pnls-default-rtdb';

async function call(host, method, path, body) {
  const url = new URL(`http://${host}/${path.replace(/^\/+/, '')}.json`);
  url.searchParams.set('ns', DATABASE_NAMESPACE);
  const response = await fetch(url, {
    method,
    headers: { Authorization: 'Bearer owner' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(
      `${method} ${path} failed with ${response.status}: ${await response.text()}`,
    );
  }
  return response.json();
}

/** Lets anyone read and write, like the dashboard's own tests need; production rules don't matter here. */
export function allowAllRules(host) {
  return call(host, 'PUT', '.settings/rules', {
    rules: { '.read': true, '.write': true },
  });
}

export function clearDatabase(host) {
  return call(host, 'DELETE', '');
}

export function setValue(host, path, value) {
  return call(host, 'PUT', path, value);
}

/** Adds a child with a push key, as the collector does, and returns the key. */
export async function pushValue(host, path, value) {
  const { name } = await call(host, 'POST', path, value);
  return name;
}
