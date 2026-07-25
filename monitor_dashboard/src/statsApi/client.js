import { auth } from '../firebase/firebase';

const API_BASE_URL = import.meta.env.VITE_STATS_API_URL;

// De-duplicate identical GET requests that are in flight at the same time.
// When two components mount together and request the same endpoint, they
// share a single network call instead of hitting the API twice.
const inFlightRequests = new Map();

async function getAuthToken() {
  const user = auth.currentUser;

  if (!user) {
    throw new Error('No authenticated user; cannot call the stats API.');
  }

  return user.getIdToken();
}

function buildUrl(path, params) {
  const url = new URL(`${API_BASE_URL}${path}`);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.append(key, value);
      }
    });
  }

  return url.toString();
}

/**
 * Performs a GET request against the stats API.
 * By default, the Firebase ID token is attached as a Bearer token.
 *
 * @param {string} path - Endpoint path, e.g. "/stats/total".
 * @param {Object} [params] - Optional query parameters.
 * @param {Object} [options] - Optional request options.
 * @param {boolean} [options.auth=true] - Attach Firebase Bearer token.
 * @param {AbortSignal} [options.signal] - Optional abort signal.
 * @param {RequestCache} [options.cache] - Optional fetch cache mode.
 * @returns {Promise<any>} Parsed JSON response.
 */
export async function apiGet(path, params, options = {}) {
  const url = buildUrl(path, params);
  const { auth: withAuth = true, signal, cache } = options;
  const requestKey = `${withAuth ? 'auth' : 'public'}:${url}`;

  if (inFlightRequests.has(requestKey)) {
    return inFlightRequests.get(requestKey);
  }

  const request = (async () => {
    const headers = {
      'Content-Type': 'application/json',
    };
    if (withAuth) {
      const token = await getAuthToken();
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers,
      signal,
      cache,
    });

    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new Error(
        `Stats API GET ${path} failed with ${response.status}: ${body}`,
      );
    }

    return response.json();
  })();

  inFlightRequests.set(requestKey, request);

  try {
    return await request;
  } finally {
    inFlightRequests.delete(requestKey);
  }
}

/**
 * Performs an authenticated GET request and returns a binary payload.
 *
 * @param {string} path - Endpoint path.
 * @param {Object} [params] - Optional query parameters.
 * @returns {Promise<{ blob: Blob, filename: string | null }>}
 */
export async function apiDownload(path, params) {
  const url = buildUrl(path, params);
  const token = await getAuthToken();

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(
      `Stats API download ${path} failed with ${response.status}: ${body}`,
    );
  }

  const contentDisposition = response.headers.get('content-disposition') ?? '';
  const filenameMatch = contentDisposition.match(
    /filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/i,
  );
  const rawFilename = filenameMatch?.[1] ?? filenameMatch?.[2] ?? null;
  const filename = rawFilename ? decodeURIComponent(rawFilename) : null;

  return {
    blob: await response.blob(),
    filename,
  };
}
