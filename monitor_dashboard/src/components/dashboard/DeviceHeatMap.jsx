import { useEffect, useMemo } from 'react';
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';

// FIXME: Maybe in the future remove hard-coded CERN Meyrin location.
const CERN_CENTER = [46.2319, 6.0555];
const CERN_BOUNDS = [
  [46.221, 6.035],
  [46.241, 6.075],
];

function parseCoordinates(coordinates) {
  if (!coordinates || typeof coordinates !== 'string') return null;
  const [latRaw, lngRaw] = coordinates.split(',');
  if (latRaw == null || lngRaw == null) return null;

  const lat = Number(latRaw.trim());
  const lng = Number(lngRaw.trim());

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return [lat, lng];
}

function HeatLayer({ points, maxIntensity }) {
  const map = useMap();

  useEffect(() => {
    if (!points.length) return undefined;

    const layer = L.heatLayer(points, {
      radius: 35,
      blur: 24,
      // Keep color intensity consistent at the dashboard zoom level.
      maxZoom: 15,
      max: maxIntensity,
      minOpacity: 0.35,
      gradient: {
        0.05: '#2c7bb6',
        0.2: '#00a6ca',
        0.3: '#90eb9d',
        0.6: '#f9d057',
        0.8: '#f29e2e',
        1.0: '#e51616',
      },
    }).addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [map, maxIntensity, points]);

  return null;
}

export default function DeviceHeatMap({ totalsPerDeviceData }) {
  const devicePoints = useMemo(() => {
    if (!totalsPerDeviceData) return [];

    return Object.entries(totalsPerDeviceData)
      .map(([deviceName, device]) => {
        const parsed = parseCoordinates(device?.coordinates);
        if (!parsed) return null;
        const [lat, lng] = parsed;
        const weight = Number(device?.probe_requests ?? 0);

        return {
          deviceName,
          lat,
          lng,
          weight,
          location: device?.location ?? 'Unknown location',
          coordinates: device?.coordinates ?? null,
        };
      })
      .filter((point) => point && point.weight > 0);
  }, [totalsPerDeviceData]);

  const heatPoints = useMemo(() => {
    if (!devicePoints.length) return [];

    const maxProbeRequests = Math.max(
      ...devicePoints.map((point) => point.weight),
      1,
    );

    return devicePoints.map((point) => {
      const normalizedWeight =
        maxProbeRequests > 0 ? point.weight / maxProbeRequests : 0;
      return [point.lat, point.lng, normalizedWeight];
    });
  }, [devicePoints]);

  return (
    <MapContainer
      center={CERN_CENTER}
      zoom={15}
      minZoom={14}
      maxZoom={18}
      maxBounds={CERN_BOUNDS}
      maxBoundsViscosity={1.0}
      style={{ height: 360, width: '100%', borderRadius: 8 }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <HeatLayer points={heatPoints} maxIntensity={1} />
      {devicePoints.map((point) => (
        <CircleMarker
          key={point.deviceName}
          center={[point.lat, point.lng]}
          radius={8}
          pathOptions={{
            color: '#0d47a1',
            weight: 1,
            fillColor: '#1976d2',
            fillOpacity: 0.08,
          }}
        >
          <Tooltip direction="top" offset={[0, -6]} opacity={0.95}>
            <div>
              <div>{point.deviceName}</div>
              <div>{point.location}</div>
              <div>{point.weight.toLocaleString()} probe requests</div>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
