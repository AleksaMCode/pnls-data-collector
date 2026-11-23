import { useEffect, useMemo } from 'react';
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const WORLD_CENTER = [20, 0];
const WORLD_ZOOM = 2;
// Published coordinates are rounded to about 1 km, so zooming in further
// would suggest a precision the data does not have.
const MAX_ZOOM = 10;

// Keeps only entries with usable coordinates.
function toPoints(geo) {
  if (!Array.isArray(geo)) return [];

  return geo
    .map((entry) => ({
      lat: Number(entry?.lat),
      lon: Number(entry?.lon),
      country: entry?.cc ?? null,
    }))
    .filter(
      (point) => Number.isFinite(point.lat) && Number.isFinite(point.lon),
    );
}

// Moves the view to the current pins, or back to the world view without pins.
function FitToPoints({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!points.length) {
      map.setView(WORLD_CENTER, WORLD_ZOOM);
      return;
    }

    map.fitBounds(
      points.map((point) => [point.lat, point.lon]),
      { padding: [40, 40], maxZoom: 8 },
    );
  }, [map, points]);

  return null;
}

export default function SsidGeoMap({ geo }) {
  const points = useMemo(() => toPoints(geo), [geo]);

  return (
    <MapContainer
      center={WORLD_CENTER}
      zoom={WORLD_ZOOM}
      minZoom={1}
      maxZoom={MAX_ZOOM}
      worldCopyJump
      style={{ height: 420, width: '100%', borderRadius: 8 }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToPoints points={points} />
      {points.map((point) => (
        <CircleMarker
          key={`${point.lat},${point.lon}`}
          center={[point.lat, point.lon]}
          radius={7}
          pathOptions={{
            color: '#0d47a1',
            weight: 2,
            fillColor: '#1976d2',
            fillOpacity: 0.6,
          }}
        >
          <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
            <div>
              {point.country && <div>{point.country}</div>}
              <div>
                {point.lat.toFixed(2)}, {point.lon.toFixed(2)}
              </div>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
