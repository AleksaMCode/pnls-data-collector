-- Reduced SSID geolocations published by the `stats` service.
-- `geo` holds one list per SSID: [{"lat": 48.85, "lon": 2.35, "cc": "FRA"}, ...]
-- and stays NULL when the SSID has no geolocation.
-- `geo_updated` is the date the geolocation was created by `ssid-geo-mapper`;
-- its maximum is the watermark the `stats` service publishes from.
alter table public.ssid_stats
  add column if not exists geo jsonb,
  add column if not exists geo_updated date;

-- Derived from `geo`, so it can never drift from the data.
alter table public.ssid_stats
  add column if not exists has_geo boolean
    generated always as (geo is not null) stored;

-- Serves "SSIDs with geolocation first, most recent first" (backward scan)
-- and its mirror (forward scan).
create index if not exists idx_ssid_stats_has_geo_last_seen
  on public.ssid_stats (has_geo, last_seen);

-- Serves the max(geo_updated) watermark lookup.
create index if not exists idx_ssid_stats_geo_updated
  on public.ssid_stats (geo_updated)
  where geo_updated is not null;
