// Unit tests of the two Leaflet maps, with Leaflet replaced by stand-ins that render the map's inputs.
import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { heatLayers } from '../../../test/support/leafletHeatStub';
import { fakeMap } from '../../../test/support/reactLeafletStub';
import DeviceHeatMap from './DeviceHeatMap';
import SsidGeoMap from './SsidGeoMap';

vi.mock(
  'react-leaflet',
  () => import('../../../test/support/reactLeafletStub'),
);
vi.mock('leaflet.heat', () => import('../../../test/support/leafletHeatStub'));

function markers() {
  return screen.queryAllByTestId('map-marker');
}

function centerOf(marker) {
  return JSON.parse(marker.dataset.center);
}

beforeEach(() => {
  heatLayers.length = 0;
  Object.values(fakeMap).forEach((fn) => fn.mockClear());
});

describe('DeviceHeatMap', () => {
  const devices = {
    'RPI-1': {
      probe_requests: 1000,
      location: 'Users Office',
      coordinates: '46.23, 6.04',
    },
    'RPI-2': { probe_requests: 250, location: null, coordinates: '46.24,6.05' },
    // Not drawn: no coordinates, unreadable coordinates, or nothing captured.
    'RPI-3': { probe_requests: 500, coordinates: null },
    'RPI-4': { probe_requests: 500, coordinates: 'north,east' },
    'RPI-5': { probe_requests: 500, coordinates: '46.2' },
    'RPI-6': { probe_requests: 0, coordinates: '46.23,6.06' },
  };

  it('centers on CERN Meyrin', () => {
    render(<DeviceHeatMap totalsPerDeviceData={null} />);

    expect(JSON.parse(screen.getByTestId('map').dataset.center)).toEqual([
      46.2319, 6.0555,
    ]);
  });

  it('marks each device that has coordinates and captured something', () => {
    render(<DeviceHeatMap totalsPerDeviceData={devices} />);

    expect(markers().map(centerOf)).toEqual([
      [46.23, 6.04],
      [46.24, 6.05],
    ]);
    const tooltip = within(markers()[0]).getByTestId('map-tooltip');
    expect(tooltip).toHaveTextContent('RPI-1');
    expect(tooltip).toHaveTextContent('Users Office');
    expect(tooltip).toHaveTextContent(
      `${(1000).toLocaleString()} probe requests`,
    );
    expect(within(markers()[1]).getByTestId('map-tooltip')).toHaveTextContent(
      'Unknown location',
    );
  });

  it('weights the heat by probe requests, relative to the busiest device', () => {
    render(<DeviceHeatMap totalsPerDeviceData={devices} />);

    expect(heatLayers).toHaveLength(1);
    expect(heatLayers[0].points).toEqual([
      [46.23, 6.04, 1],
      [46.24, 6.05, 0.25],
    ]);
    expect(fakeMap.addLayer).toHaveBeenCalledWith(heatLayers[0]);
  });

  it('adds no heat layer without devices to draw', () => {
    render(
      <DeviceHeatMap totalsPerDeviceData={{ 'RPI-3': devices['RPI-3'] }} />,
    );

    expect(heatLayers).toHaveLength(0);
    expect(markers()).toHaveLength(0);
  });

  it('replaces the heat layer when the data changes, and removes it on unmount', () => {
    const { rerender, unmount } = render(
      <DeviceHeatMap totalsPerDeviceData={devices} />,
    );

    rerender(
      <DeviceHeatMap
        totalsPerDeviceData={{
          ...devices,
          'RPI-2': { ...devices['RPI-2'], probe_requests: 2000 },
        }}
      />,
    );
    expect(fakeMap.removeLayer).toHaveBeenCalledWith(heatLayers[0]);
    expect(heatLayers[1].points).toEqual([
      [46.23, 6.04, 0.5],
      [46.24, 6.05, 1],
    ]);

    unmount();
    expect(fakeMap.removeLayer).toHaveBeenCalledWith(heatLayers[1]);
  });
});

describe('SsidGeoMap', () => {
  it('shows the world without pins when no SSID is selected', () => {
    render(<SsidGeoMap geo={null} />);

    expect(markers()).toHaveLength(0);
    expect(fakeMap.setView).toHaveBeenCalledWith([20, 0], 2);
    expect(fakeMap.fitBounds).not.toHaveBeenCalled();
  });

  it('pins each location and zooms to fit them', () => {
    render(
      <SsidGeoMap
        geo={[
          { lat: 46.2044, lon: 6.1432, cc: 'CH' },
          { lat: '48.8566', lon: '2.3522' },
        ]}
      />,
    );

    expect(markers().map(centerOf)).toEqual([
      [46.2044, 6.1432],
      [48.8566, 2.3522],
    ]);
    expect(within(markers()[0]).getByTestId('map-tooltip')).toHaveTextContent(
      'CH46.20, 6.14',
    );
    expect(within(markers()[1]).getByTestId('map-tooltip')).toHaveTextContent(
      /^48\.86, 2\.35$/,
    );
    expect(fakeMap.fitBounds).toHaveBeenCalledWith(
      [
        [46.2044, 6.1432],
        [48.8566, 2.3522],
      ],
      { padding: [40, 40], maxZoom: 8 },
    );
  });

  it('skips locations without usable coordinates', () => {
    render(
      <SsidGeoMap
        geo={[
          { lat: 46.2, lon: 6.1 },
          { lat: 'north', lon: 6.1 },
          { lon: 6.1 },
          null,
        ]}
      />,
    );

    expect(markers().map(centerOf)).toEqual([[46.2, 6.1]]);
  });

  it.fails(
    'skips a location whose latitude is null. Known bug: Number(null) is 0, so it is pinned on the equator',
    () => {
      render(<SsidGeoMap geo={[{ lat: null, lon: 6.1 }]} />);

      expect(markers()).toHaveLength(0);
    },
  );

  it('goes back to the world view when the selection is cleared', () => {
    const { rerender } = render(<SsidGeoMap geo={[{ lat: 46.2, lon: 6.1 }]} />);

    rerender(<SsidGeoMap geo={null} />);

    expect(markers()).toHaveLength(0);
    expect(fakeMap.setView).toHaveBeenLastCalledWith([20, 0], 2);
  });
});
