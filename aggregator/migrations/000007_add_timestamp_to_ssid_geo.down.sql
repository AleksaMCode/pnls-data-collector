ALTER TABLE public.ssid_geo_reduced
    DROP COLUMN IF EXISTS created_date;

ALTER TABLE public.ssid_geo
    DROP COLUMN IF EXISTS created_date;