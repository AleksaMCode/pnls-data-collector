// Integration tests of signing in and out, and of which routes need a signed-in viewer.
import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { fakeAuth } from '../support/fakeFirebase/auth';
import { currentPath, renderApp, VIEWER } from '../support/renderApp';
import { fixtures, requests, requestsTo } from '../support/statsApi';

function emailField() {
  return screen.getByPlaceholderText('name@email.com');
}

function passwordField() {
  return screen.getByPlaceholderText('********');
}

/** Types into the fields (an empty string leaves a field as it is) and submits. */
async function signIn(user, email, password) {
  if (email)
    await user.type(
      await screen.findByPlaceholderText('name@email.com'),
      email,
    );
  if (password) await user.type(passwordField(), password);
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('routes', () => {
  it.each(['/home', '/ssids', '/device/RPI-1', '/'])(
    'sends a signed-out viewer from %s to the sign-in page',
    async (route) => {
      renderApp({ route, signedIn: false });

      expect(
        await screen.findByText(
          'Sign in to continue to the PNLS-DC Monitoring Dashboard',
        ),
      ).toBeInTheDocument();
      expect(currentPath()).toBe('/login');
    },
  );

  it('calls no stats endpoint before the viewer signs in', async () => {
    renderApp({ route: '/home', signedIn: false });
    await screen.findByPlaceholderText('name@email.com');

    expect(requests.filter((r) => r.path !== '/health')).toEqual([]);
  });

  it('sends a signed-in viewer from the sign-in page to the dashboard', async () => {
    renderApp({ route: '/login' });

    await waitFor(() => expect(currentPath()).toBe('/home'));
  });

  it('opens the home page at the root', async () => {
    renderApp({ route: '/' });

    await waitFor(() => expect(currentPath()).toBe('/home'));
  });

  it('sends an unknown path to the dashboard when signed in', async () => {
    renderApp({ route: '/no/such/page' });

    await waitFor(() => expect(currentPath()).toBe('/home'));
  });
});

describe('sign-in page', () => {
  it('warms up the stats API without a token', async () => {
    renderApp({ route: '/login', signedIn: false });

    await waitFor(() => expect(requestsTo('/health')).toHaveLength(1));
    expect(requestsTo('/health')[0].authorization).toBeNull();
  });

  it('signs in and opens the dashboard with the viewer’s token', async () => {
    const { user } = renderApp({ route: '/login', signedIn: false });

    await signIn(user, VIEWER.email, VIEWER.password);

    await waitFor(() => expect(currentPath()).toBe('/home'));
    // The all-time total, on its card and on the monthly chart.
    expect(
      await screen.findAllByText(
        fixtures.total.probeRequestCount.toLocaleString(),
      ),
    ).not.toHaveLength(0);
    const statsRequests = requests.filter((r) => r.path !== '/health');
    expect(statsRequests.length).toBeGreaterThan(0);
    expect(new Set(statsRequests.map((r) => r.authorization))).toEqual(
      new Set([`Bearer test-id-token:${VIEWER.email}`]),
    );
  });

  it('shows the viewer’s name from their email in the side menu', async () => {
    fakeAuth.addUser('jane.doe+cern@example.test', 'secret-password');
    const { user } = renderApp({ route: '/login', signedIn: false });

    await signIn(user, 'jane.doe+cern@example.test', 'secret-password');

    expect(await screen.findByText('Jane Doe')).toBeInTheDocument();
  });

  it('checks the fields before calling Firebase', async () => {
    const { user } = renderApp({ route: '/login', signedIn: false });
    await screen.findByPlaceholderText('name@email.com');

    await signIn(user, 'not-an-email', '123');

    expect(
      screen.getByText('Please enter a valid email address.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Password must be at least 6 characters long.'),
    ).toBeInTheDocument();
    expect(fakeAuth.currentUser).toBeNull();
    expect(currentPath()).toBe('/login');
  });

  it('clears a field error once the field is fixed', async () => {
    const { user } = renderApp({ route: '/login', signedIn: false });
    await screen.findByPlaceholderText('name@email.com');
    await signIn(user, 'not-an-email', VIEWER.password);

    await user.clear(emailField());
    await signIn(user, VIEWER.email, '');

    expect(
      screen.queryByText('Please enter a valid email address.'),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(currentPath()).toBe('/home'));
  });

  it('says so when Firebase rejects the credentials, and lets the viewer try again', async () => {
    const { user } = renderApp({ route: '/login', signedIn: false });
    await screen.findByPlaceholderText('name@email.com');

    await signIn(user, VIEWER.email, 'wrong-password');

    expect(
      await screen.findByText('Failed to sign in. Please try again.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled();

    await user.clear(passwordField());
    await signIn(user, '', VIEWER.password);
    await waitFor(() => expect(currentPath()).toBe('/home'));
  });

  it('shows and hides the password', async () => {
    const { user } = renderApp({ route: '/login', signedIn: false });
    await user.type(await screen.findByPlaceholderText('********'), 'secret');

    const toggle = passwordField()
      .closest('.MuiInputBase-root')
      .querySelector('button');
    await user.click(toggle);
    expect(passwordField()).toHaveAttribute('type', 'text');

    await user.click(toggle);
    expect(passwordField()).toHaveAttribute('type', 'password');
  });

  it.fails(
    'labels its fields and buttons for screen readers. Known bug: the labels are not tied to the inputs',
    async () => {
      renderApp({ route: '/login', signedIn: false });
      await screen.findByPlaceholderText('name@email.com');

      expect(screen.getByLabelText('Email')).toBe(emailField());
      expect(screen.getByLabelText('Password')).toBe(passwordField());
      expect(
        screen.getByRole('button', { name: /show password/i }),
      ).toBeInTheDocument();
    },
  );
});

describe('signing out', () => {
  async function signOut(user) {
    await user.click(await screen.findByRole('button', { name: 'Open menu' }));
    await user.click(
      within(await screen.findByRole('menu')).getByText('Logout'),
    );
  }

  it('signs out from the menu and returns to the sign-in page', async () => {
    const { user } = renderApp({ route: '/home' });

    await signOut(user);

    await waitFor(() => expect(currentPath()).toBe('/login'));
    expect(fakeAuth.currentUser).toBeNull();
  });

  it.fails(
    'forgets the stats of the viewer who signed out. Known bug: the query cache outlives the session',
    async () => {
      const { user } = renderApp({ route: '/home' });
      await screen.findAllByText(
        fixtures.total.probeRequestCount.toLocaleString(),
      );
      await signOut(user);
      await waitFor(() => expect(currentPath()).toBe('/login'));
      const before = requestsTo('/stats/total').length;

      await signIn(user, VIEWER.email, VIEWER.password);
      await waitFor(() => expect(currentPath()).toBe('/home'));

      await waitFor(() =>
        expect(requestsTo('/stats/total').length).toBe(before + 1),
      );
    },
  );
});
