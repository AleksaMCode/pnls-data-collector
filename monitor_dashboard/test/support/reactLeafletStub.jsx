// Stand-ins for react-leaflet: jsdom can't lay out a Leaflet map, so these render the map's inputs as
// plain elements that tests can read.
import { vi } from 'vitest';

export const fakeMap = {
  setView: vi.fn(),
  fitBounds: vi.fn(),
  addLayer: vi.fn(),
  removeLayer: vi.fn(),
};

export function MapContainer({ children, center, zoom }) {
  return (
    <div
      data-testid="map"
      data-center={JSON.stringify(center)}
      data-zoom={zoom}
    >
      {children}
    </div>
  );
}

export function TileLayer({ url }) {
  return <div data-testid="map-tiles" data-url={url} />;
}

export function CircleMarker({ center, children }) {
  return (
    <div data-testid="map-marker" data-center={JSON.stringify(center)}>
      {children}
    </div>
  );
}

export function Tooltip({ children }) {
  return <div data-testid="map-tooltip">{children}</div>;
}

export function useMap() {
  return fakeMap;
}
