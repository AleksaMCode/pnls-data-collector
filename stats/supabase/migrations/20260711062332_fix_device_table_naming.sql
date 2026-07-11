drop table if exists public.location_mapping_resolved;
create table if not exists public.devices (
  device varchar primary key,
  location varchar not null,
  coordinates varchar null
);