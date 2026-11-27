// Unit tests of the live-view switch state shared by the header and the pages.
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { expect, it } from 'vitest';
import { LiveCountProvider, useLiveCount } from './LiveCountProvider';

function Probe() {
  const { enabled, setEnabled } = useLiveCount();
  const navigate = useNavigate();
  return (
    <>
      <output>{enabled ? 'on' : 'off'}</output>
      <button onClick={() => setEnabled(true)}>enable</button>
      <button onClick={() => navigate('/ssids')}>navigate</button>
    </>
  );
}

function renderProvider() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <LiveCountProvider>
        <Probe />
      </LiveCountProvider>
    </MemoryRouter>,
  );
}

it('starts with live view off', () => {
  renderProvider();

  expect(screen.getByRole('status')).toHaveTextContent('off');
});

it('turns live view off when the page changes', async () => {
  const user = userEvent.setup();
  renderProvider();

  await user.click(screen.getByText('enable'));
  expect(screen.getByRole('status')).toHaveTextContent('on');

  await user.click(screen.getByText('navigate'));
  expect(screen.getByRole('status')).toHaveTextContent('off');
});

it('is off and inert outside a provider', async () => {
  const user = userEvent.setup();
  function Outside() {
    const { enabled, setEnabled } = useLiveCount();
    return (
      <button onClick={() => setEnabled(true)}>{enabled ? 'on' : 'off'}</button>
    );
  }
  render(<Outside />);

  await user.click(screen.getByRole('button', { name: 'off' }));

  expect(screen.getByRole('button')).toHaveTextContent('off');
});
