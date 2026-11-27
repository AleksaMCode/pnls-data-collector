// Integration tests of a device's page: its totals, and its live table of probed SSIDs.
import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { fakeDatabase } from '../support/fakeFirebase/database';
import { deviceNode } from '../support/paris';
import { currentPath, renderApp } from '../support/renderApp';
import { fixtures, requestsTo, TODAY } from '../support/statsApi';

function totalCard(title) {
  const cards = screen
    .getAllByText(title, { selector: 'h2' })
    .map((heading) => heading.closest('.MuiCard-root'));
  expect(cards).toHaveLength(1);
  return cards[0];
}

async function waitForTotals() {
  await waitFor(() =>
    expect(
      within(totalCard('Probe Requests')).getByText('45'),
    ).toBeInTheDocument(),
  );
}

function addRow(ssid, time) {
  fakeDatabase.push(`${deviceNode('RPI-1', TODAY)}/data`, {
    ssid,
    timestamp: `${TODAY} ${time}`,
  });
}

/** The SSIDs in the live table, oldest first. */
function liveSsids() {
  const table = screen.getByRole('table');
  return within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).queryAllByRole('cell')[0]?.textContent)
    .filter(Boolean);
}

async function turnOnLiveView(user) {
  await user.click(
    await screen.findByRole('switch', {
      name: 'Toggle to view live Probe Request data',
    }),
  );
}

describe('device page', () => {
  it('shows the device name and its probe requests up to yesterday', async () => {
    renderApp({ route: '/device/RPI-1' });

    expect(await screen.findByText('Device: RPI-1')).toBeInTheDocument();
    // 0 + 20 + 15 + 10: today's row is left out by the API.
    await waitForTotals();
    expect(requestsTo('/stats/series/RPI-1')).toHaveLength(1);
  });

  it.fails(
    'shows the unique SSID and MAC totals of the grid. Known bug: it adds up daily unique counts',
    async () => {
      renderApp({ route: '/device/RPI-1' });
      await waitForTotals();

      expect(
        within(totalCard('SSIDs')).getByText(
          String(fixtures.devices['RPI-1'].ssid),
        ),
      ).toBeInTheDocument();
      expect(
        within(totalCard('MAC addresses')).getByText(
          String(fixtures.devices['RPI-1'].mac),
        ),
      ).toBeInTheDocument();
    },
  );

  it('sends an unknown device to the home page without asking for its series', async () => {
    renderApp({ route: '/device/RPI-9' });

    await waitFor(() => expect(currentPath()).toBe('/home'));
    expect(requestsTo('/stats/series/RPI-9')).toHaveLength(0);
  });

  it('opens a device from the side menu', async () => {
    const { user } = renderApp({ route: '/home' });

    await user.click(await screen.findByRole('button', { name: 'Devices' }));
    await user.click(await screen.findByRole('button', { name: 'RPI-2' }));

    await waitFor(() => expect(currentPath()).toBe('/device/RPI-2'));
    expect(await screen.findByText('Device: RPI-2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'RPI-2' })).toHaveClass(
      'Mui-selected',
    );
  });
});

describe('live table', () => {
  it("shows the latest SSID and every new one, without CERN's own networks", async () => {
    addRow('Old', '09:00:00');
    addRow('Latest', '09:30:00');
    const { user } = renderApp({ route: '/device/RPI-1' });
    await waitForTotals();
    expect(liveSsids()).toEqual([]);

    await turnOnLiveView(user);
    await waitFor(() => expect(liveSsids()).toEqual(['Latest']));

    addRow('CERN', '10:00:01');
    addRow('CERN-Visitors', '10:00:02');
    addRow('*', '10:00:03');
    addRow('HomeWifi', '10:00:04');

    await waitFor(() => expect(liveSsids()).toEqual(['Latest', 'HomeWifi']));
    expect(screen.getByText(`${TODAY} 10:00:04`)).toBeInTheDocument();
  });

  it('hides SSIDs the viewer filters out, and stops filtering when the filters are cleared', async () => {
    const { user } = renderApp({ route: '/device/RPI-1' });
    await waitForTotals();
    await turnOnLiveView(user);

    await user.type(
      screen.getByPlaceholderText('Filter SSID...'),
      ' Noisy {Enter}',
    );
    expect(screen.getByText('Noisy')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Filter SSID...')).toHaveValue('');

    addRow('Noisy', '10:00:01');
    addRow('Quiet', '10:00:02');
    await waitFor(() => expect(liveSsids()).toEqual(['Quiet']));

    await user.click(screen.getByText('Clear all'));
    expect(
      screen.queryByText('Noisy', { selector: '.MuiChip-label' }),
    ).toBeNull();
    addRow('CERN', '10:00:03');
    await waitFor(() => expect(liveSsids()).toEqual(['Quiet', 'CERN']));
  });

  it('removes one filter with its chip', async () => {
    const { user } = renderApp({ route: '/device/RPI-1' });
    await waitForTotals();
    await turnOnLiveView(user);

    const chip = screen.getByText('CERN', { selector: '.MuiChip-label' });
    await user.click(chip.parentElement.querySelector('.MuiChip-deleteIcon'));
    addRow('CERN', '10:00:01');

    await waitFor(() => expect(liveSsids()).toEqual(['CERN']));
    expect(screen.getByText('CERN-Visitors')).toBeInTheDocument();
  });

  it('adds the same filter only once', async () => {
    const { user } = renderApp({ route: '/device/RPI-1' });
    await waitForTotals();

    await user.type(
      screen.getByPlaceholderText('Filter SSID...'),
      'CERN{Enter}',
    );

    expect(
      screen.getAllByText('CERN', { selector: '.MuiChip-label' }),
    ).toHaveLength(1);
  });

  it('stops listening when live view is turned off', async () => {
    const { user } = renderApp({ route: '/device/RPI-1' });
    await waitForTotals();

    await turnOnLiveView(user);
    expect(fakeDatabase.listenedPaths()).toEqual([
      `${deviceNode('RPI-1', TODAY)}/data`,
    ]);
    await turnOnLiveView(user);

    expect(fakeDatabase.listenedPaths()).toEqual([]);
  });
});
