// Unit tests of the stats API client: URLs, the Firebase token, shared requests and errors.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiDownload, apiGet } from './client';

const auth = vi.hoisted(() => ({ currentUser: null }));
vi.mock('../firebase/firebase', () => ({ auth }));

const API = 'http://stats-api.test';

function jsonResponse(body, init = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

let fetchMock;

beforeEach(() => {
  auth.currentUser = { getIdToken: vi.fn(async () => 'id-token') };
  fetchMock = vi.fn(async () => jsonResponse({ ok: true }));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiGet', () => {
  it('calls the API with the Firebase ID token and returns the JSON body', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ macCount: 9 }));

    await expect(apiGet('/stats/total')).resolves.toEqual({ macCount: 9 });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API}/stats/total`);
    expect(init.method).toBe('GET');
    expect(init.headers.Authorization).toBe('Bearer id-token');
  });

  it('sends query parameters and leaves out empty ones', async () => {
    await apiGet('/stats/ssids', {
      search: 'cern',
      offset: 0,
      empty: '',
      missing: undefined,
      nothing: null,
    });

    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(Object.fromEntries(url.searchParams)).toEqual({
      search: 'cern',
      offset: '0',
    });
  });

  it('encodes query parameters', async () => {
    await apiGet('/stats/ssids', { search: 'Café & Co?' });

    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.searchParams.get('search')).toBe('Café & Co?');
  });

  it('fails without a signed-in user and calls nothing', async () => {
    auth.currentUser = null;

    await expect(apiGet('/stats/total')).rejects.toThrow(
      'No authenticated user',
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('sends no token for public endpoints, even when signed out', async () => {
    auth.currentUser = null;

    await apiGet('/health', undefined, { auth: false });

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it('passes the abort signal and cache mode to fetch', async () => {
    const controller = new AbortController();

    await apiGet('/health', undefined, {
      auth: false,
      signal: controller.signal,
      cache: 'no-store',
    });

    const init = fetchMock.mock.calls[0][1];
    expect(init.signal).toBe(controller.signal);
    expect(init.cache).toBe('no-store');
  });

  it('shares one request between identical calls in flight', async () => {
    let resolve;
    fetchMock.mockReturnValueOnce(
      new Promise((r) => {
        resolve = r;
      }),
    );

    const first = apiGet('/stats/total');
    const second = apiGet('/stats/total');
    // The token is fetched asynchronously before fetch is called.
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    resolve(jsonResponse({ shared: true }));

    await expect(Promise.all([first, second])).resolves.toEqual([
      { shared: true },
      { shared: true },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('makes a new request once the shared one has finished', async () => {
    await apiGet('/stats/total');
    await apiGet('/stats/total');

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('keeps requests with different parameters or auth apart', async () => {
    await Promise.all([
      apiGet('/stats/ssids', { offset: 0 }),
      apiGet('/stats/ssids', { offset: 25 }),
      apiGet('/health', undefined, { auth: false }),
      apiGet('/health'),
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it('reports the status and body of a failed request', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('{"detail":"Invalid or expired Firebase token."}', {
        status: 401,
      }),
    );

    await expect(apiGet('/stats/total')).rejects.toThrow(
      'Stats API GET /stats/total failed with 401: {"detail":"Invalid or expired Firebase token."}',
    );
  });

  it('forgets a failed request, so the next call tries again', async () => {
    fetchMock.mockResolvedValueOnce(new Response('', { status: 503 }));
    await expect(apiGet('/stats/total')).rejects.toThrow('503');

    await expect(apiGet('/stats/total')).resolves.toEqual({ ok: true });
  });

  it('rejects when the network fails', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('fetch failed'));

    await expect(apiGet('/stats/total')).rejects.toThrow('fetch failed');
  });
});

describe('apiDownload', () => {
  function csvResponse(contentDisposition) {
    const headers = { 'Content-Type': 'text/csv' };
    if (contentDisposition) headers['Content-Disposition'] = contentDisposition;
    return new Response('ssid\nCERN\n', { status: 200, headers });
  }

  it('returns the file and the file name the API gives', async () => {
    fetchMock.mockResolvedValueOnce(
      csvResponse('attachment; filename="ssid_stats_2026-06-15.csv"'),
    );

    const { blob, filename } = await apiDownload('/stats/ssids/export', {
      search: 'cern',
    });

    expect(filename).toBe('ssid_stats_2026-06-15.csv');
    await expect(blob.text()).resolves.toBe('ssid\nCERN\n');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API}/stats/ssids/export?search=cern`);
    expect(init.headers.Authorization).toBe('Bearer id-token');
  });

  it('reads an unquoted file name', async () => {
    fetchMock.mockResolvedValueOnce(
      csvResponse('attachment; filename=export.csv'),
    );

    await expect(apiDownload('/x')).resolves.toMatchObject({
      filename: 'export.csv',
    });
  });

  it('decodes a UTF-8 file name', async () => {
    fetchMock.mockResolvedValueOnce(
      csvResponse("attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.csv"),
    );

    await expect(apiDownload('/x')).resolves.toMatchObject({
      filename: 'résumé.csv',
    });
  });

  it('returns no file name when the API gives none', async () => {
    fetchMock.mockResolvedValueOnce(csvResponse(null));

    await expect(apiDownload('/x')).resolves.toMatchObject({ filename: null });
  });

  it('reports a failed download', async () => {
    fetchMock.mockResolvedValueOnce(new Response('nope', { status: 500 }));

    await expect(apiDownload('/stats/ssids/export')).rejects.toThrow(
      'Stats API download /stats/ssids/export failed with 500: nope',
    );
  });

  it('fails without a signed-in user', async () => {
    auth.currentUser = null;

    await expect(apiDownload('/x')).rejects.toThrow('No authenticated user');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
