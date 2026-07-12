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
 * Performs an authenticated GET request against the stats API.
 * The Firebase ID token is attached as a Bearer token on every call.
 *
 * @param {string} path - Endpoint path, e.g. "/stats/total".
 * @param {Object} [params] - Optional query parameters.
 * @returns {Promise<any>} Parsed JSON response.
 */
export async function apiGet(path, params) {
  const url = buildUrl(path, params);

  if (inFlightRequests.has(url)) {
    return inFlightRequests.get(url);
  }

  const request = (async () => {
    const token = await getAuthToken();

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new Error(
        `Stats API GET ${path} failed with ${response.status}: ${body}`,
      );
    }

    return response.json();
  })();

  inFlightRequests.set(url, request);

  try {
    return await request;
  } finally {
    inFlightRequests.delete(url);
  }
}
