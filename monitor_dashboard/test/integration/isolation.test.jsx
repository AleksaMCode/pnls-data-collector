// Integration tests of the test setup itself: a test doesn't see the stats requests of the one before.
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../support/renderApp';
import { fixtures, holdRoute, requestsTo } from '../support/statsApi';

const n = (value) => value.toLocaleString();

// The two tests run in order. The stats client shares a pending request with any identical one,
// so without the teardown waiting for the first test's request, the second test's request would
// get the first one's, which is never answered.
describe('a stats request left pending by a test', () => {
  it('is pending when the test ends', async () => {
    holdRoute('/stats/total');
    renderApp();

    await screen.findAllByRole('progressbar');
  });

  it('is answered before the next test, which sends its own', async () => {
    renderApp();

    expect(
      await screen.findAllByText(n(fixtures.total.probeRequestCount)),
    ).not.toHaveLength(0);
    expect(requestsTo('/stats/total')).toHaveLength(1);
  });
});
