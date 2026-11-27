import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import App from '../../src/App';
import { queryClient as productionQueryClient } from '../../src/queryClient';
import { fakeAuth } from './fakeFirebase/auth';
import { allowUser } from './statsApi';

export const VIEWER = {
  email: 'viewer@example.test',
  password: 'correct-horse',
};

function LocationDisplay() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

/** The path the app is showing. */
export function currentPath() {
  return screen.getByTestId('location').textContent;
}

/**
 * Renders the whole app at a route, as main.jsx does, with a fresh query cache that uses the
 * production defaults. The viewer starts signed in unless `signedIn` is false.
 */
export function renderApp({ route = '/home', signedIn = true } = {}) {
  fakeAuth.addUser(VIEWER.email, VIEWER.password);
  allowUser(VIEWER.email);
  if (signedIn) {
    fakeAuth.signInAs(VIEWER.email);
  }

  const queryClient = new QueryClient({
    defaultOptions: productionQueryClient.getDefaultOptions(),
  });
  const user = userEvent.setup();
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
        <LocationDisplay />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, user, queryClient };
}
