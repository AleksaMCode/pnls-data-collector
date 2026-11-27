// Integration tests of the dashboard frame: side menu, breadcrumbs, header controls and language.
import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { currentPath, renderApp } from '../support/renderApp';

const LIVE_SWITCH = { name: 'Toggle to view live Probe Request data' };

function breadcrumbs() {
  return within(screen.getByRole('navigation', { name: 'breadcrumb' }));
}

describe('side menu', () => {
  it('lists the devices the API returns, sorted', async () => {
    const { user } = renderApp();

    await user.click(await screen.findByRole('button', { name: 'Devices' }));

    const items = await screen.findAllByRole('button', { name: /^RPI-\d$/ });
    expect(items.map((item) => item.textContent)).toEqual([
      'RPI-1',
      'RPI-2',
      'RPI-3',
    ]);
  });

  it('moves between pages and marks the current one', async () => {
    const { user } = renderApp();

    await user.click(await screen.findByRole('button', { name: 'SSIDs' }));
    await waitFor(() => expect(currentPath()).toBe('/ssids'));
    expect(screen.getByRole('button', { name: 'SSIDs' })).toHaveClass(
      'Mui-selected',
    );

    await user.click(screen.getByRole('button', { name: 'Home' }));
    await waitFor(() => expect(currentPath()).toBe('/home'));
    expect(screen.getByRole('button', { name: 'Home' })).toHaveClass(
      'Mui-selected',
    );
  });
});

describe('breadcrumbs', () => {
  it('show the page, with a link back to the dashboard', async () => {
    const { user } = renderApp({ route: '/device/RPI-1' });

    await screen.findByText('Device: RPI-1');
    expect(breadcrumbs().getByText('Device')).toBeInTheDocument();
    expect(breadcrumbs().getByText('RPI-1')).toBeInTheDocument();

    await user.click(breadcrumbs().getByRole('link', { name: 'Dashboard' }));
    await waitFor(() => expect(currentPath()).toBe('/home'));
    expect(breadcrumbs().getByText('Home')).toBeInTheDocument();
  });
});

describe('header', () => {
  it('hides the live switch on the SSID page, which has no live data', async () => {
    const { user } = renderApp();
    expect(await screen.findByRole('switch', LIVE_SWITCH)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'SSIDs' }));

    await waitFor(() =>
      expect(screen.queryByRole('switch', LIVE_SWITCH)).not.toBeInTheDocument(),
    );
  });

  it('switches the language of the whole page', async () => {
    const { user } = renderApp();
    await screen.findByText('Overview');

    await user.click(
      screen.getByTestId('LanguageRoundedIcon').closest('button'),
    );
    await user.click(await screen.findByRole('menuitem', { name: 'French' }));

    await waitFor(() => expect(screen.queryByText('Overview')).toBeNull());
    expect(window.localStorage.getItem('i18nextLng')).toBe('fr');
  });
});
