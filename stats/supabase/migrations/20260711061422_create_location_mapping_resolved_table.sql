create table if not exists public.location_mapping_resolved (
  device varchar primary key,
  location varchar not null,
  coordinates varchar null
);
