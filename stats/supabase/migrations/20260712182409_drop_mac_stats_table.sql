drop index if exists public.uq_mac_stats_mac;
drop index if exists public.idx_mac_stats_first_seen;
drop index if exists public.idx_mac_stats_last_seen;

drop table if exists public.mac_stats;
