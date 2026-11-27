// Unit tests of the stat card: trends, live values, loading, and the date labels of its sparkline.
import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { parisInstant } from '../../../test/support/paris';
import { useViewerTimezone } from '../../../test/support/timezone';
import StatCard, { formatDateLabels, getLastNDays } from './StatCard';

beforeEach(() => {
  vi.setSystemTime(parisInstant('2026-06-15T10:00:00'));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('getLastNDays', () => {
  it('labels the n days before today, oldest first', () => {
    const days = getLastNDays(30);

    expect(days).toHaveLength(30);
    expect(days[0]).toBe('May 16');
    expect(days.at(-1)).toBe('Jun 14');
  });

  it('uses the locale for month names', () => {
    expect(getLastNDays(1, 'fr-FR')).toEqual(['juin 14']);
    expect(getLastNDays(1, 'de-DE')).toEqual(['Jun 14']);
  });

  it('adds the year only when asked to and the range is longer than a year', () => {
    expect(getLastNDays(366, 'en-US', undefined, true).at(-1)).toBe(
      'Jun 14, 2026',
    );
    expect(getLastNDays(366, 'en-US', undefined, true)[0]).toBe('Jun 14, 2025');
    expect(getLastNDays(30, 'en-US', undefined, true).at(-1)).toBe('Jun 14');
    expect(getLastNDays(400).at(-1)).toBe('Jun 14');
  });

  it('gives every day of a long range its own label', () => {
    const days = getLastNDays(800, 'en-US', undefined, true);

    expect(new Set(days).size).toBe(800);
  });

  it.fails(
    "labels Paris's days for a viewer in another timezone. Known bug: day and month come from different timezones",
    () => {
      useViewerTimezone('America/New_York');
      // 21:00 on 1 April in New York is 03:00 on 2 April in Paris; the series ends on 1 April.
      vi.setSystemTime(new Date('2026-04-02T01:00:00Z'));

      expect(getLastNDays(2)).toEqual(['Mar 31', 'Apr 1']);
    },
  );
});

describe('formatDateLabels', () => {
  it('formats ISO dates with the year, in the locale', () => {
    expect(formatDateLabels(['2026-06-14', '2025-12-31'])).toEqual([
      'Jun 14, 2026',
      'Dec 31, 2025',
    ]);
    expect(formatDateLabels(['2026-06-14'], 'de-DE')).toEqual([
      '14. Juni 2026',
    ]);
  });

  it('keeps the calendar day in any viewer timezone', () => {
    useViewerTimezone('Pacific/Honolulu');

    expect(formatDateLabels(['2026-06-14'])).toEqual(['Jun 14, 2026']);
  });

  it('passes unreadable dates through', () => {
    expect(formatDateLabels(['not-a-date'])).toEqual(['not-a-date']);
  });
});

function renderCard(props) {
  return render(
    <StatCard
      title="Probe Requests"
      interval="Last 30 days"
      data={[1, 2, 3]}
      hideSparkLineChart
      {...props}
    />,
  );
}

function trendChip() {
  return screen.getByText(/%$/).closest('.MuiChip-root');
}

describe('StatCard trend', () => {
  it.each([
    [150, 100, '+50.0%', 'Success'],
    [100, 100, '+0.0%', 'Default'],
    [95, 100, '-5.0%', 'Default'],
    [80, 100, '-20.0%', 'Error'],
    [0, 100, '-100.0%', 'Error'],
  ])(
    'compares %d with the previous %d as %s',
    (value, prevValue, label, color) => {
      renderCard({ value, prevValue });

      expect(trendChip()).toHaveTextContent(label);
      expect(trendChip()).toHaveClass(`MuiChip-color${color}`);
    },
  );

  it('shows no change when there is no previous value', () => {
    renderCard({ value: 60, prevValue: 0 });

    expect(trendChip()).toHaveTextContent('0%');
    expect(trendChip()).toHaveClass('MuiChip-colorDefault');
  });

  it('hides the trend when asked to, or while loading', () => {
    const { rerender } = renderCard({
      value: 60,
      prevValue: 100,
      hideTrendValues: true,
    });
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();

    rerender(
      <StatCard
        title="Probe Requests"
        interval="Last 30 days"
        data={[]}
        value={60}
        prevValue={100}
        isLoading
        hideSparkLineChart
      />,
    );
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it('updates the trend when the values change', () => {
    const { rerender } = renderCard({ value: 150, prevValue: 100 });

    rerender(
      <StatCard
        title="Probe Requests"
        interval="Last 30 days"
        data={[]}
        value={50}
        prevValue={100}
        hideSparkLineChart
      />,
    );

    expect(trendChip()).toHaveTextContent('-50.0%');
  });
});

describe('StatCard value', () => {
  it('shows the formatted value, title and interval', () => {
    renderCard({ value: 1159, trend: 'up', hideTrendValues: true });

    expect(screen.getByText('Probe Requests')).toBeInTheDocument();
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
    expect(screen.getByText((1159).toLocaleString())).toBeInTheDocument();
  });

  it('shows a spinner instead of the value while loading', () => {
    renderCard({ value: 1159, trend: 'up', isLoading: true });

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByText((1159).toLocaleString())).not.toBeInTheDocument();
  });

  it('draws the sparkline unless hidden or loading', () => {
    const { container, rerender } = render(
      <StatCard title="T" interval="I" trend="up" value={3} data={[1, 2, 3]} />,
    );
    expect(container.querySelector('svg')).toBeInTheDocument();

    rerender(
      <StatCard
        title="T"
        interval="I"
        trend="up"
        value={3}
        data={[1, 2, 3]}
        isLoading
      />,
    );
    expect(container.querySelector('svg.MuiChartsSurface-root')).toBeNull();
  });
});

describe('StatCard live value', () => {
  const live = { interval: 'Live', hideTrendValues: true, trend: 'up' };

  it('shows the live value and its growth over the starting value', () => {
    renderCard({ ...live, value: 200, liveValue: 250, liveFeed: true });

    expect(screen.getByText('250')).toBeInTheDocument();
    expect(screen.getByText('+25.00%')).toBeInTheDocument();
  });

  it('shows the starting value until the live value grows past it', () => {
    renderCard({ ...live, value: 200, liveValue: 200, liveFeed: true });

    expect(screen.getByText('200')).toBeInTheDocument();
    expect(screen.queryByText(/^\+.*%$/)).not.toBeInTheDocument();
  });

  it('ignores the live value when the feed is off', () => {
    renderCard({ ...live, value: 200, liveValue: 250, liveFeed: false });

    expect(screen.getByText('200')).toBeInTheDocument();
    expect(screen.queryByText('250')).not.toBeInTheDocument();
  });

  it('shows the live badge with its interval, or "Connecting..." while loading', () => {
    const { rerender } = renderCard({ ...live, value: 0, liveFeed: true });
    expect(screen.getByText('Live')).toBeInTheDocument();

    rerender(
      <StatCard
        title="Probe Requests"
        data={[]}
        {...live}
        value={0}
        liveFeed
        isLoading
        hideSparkLineChart
      />,
    );
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
  });
});
