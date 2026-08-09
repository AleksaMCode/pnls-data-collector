ALTER TABLE public.ssid_geo
    ADD COLUMN created_date date NOT NULL DEFAULT CURRENT_DATE;

ALTER TABLE public.ssid_geo_reduced
    ADD COLUMN created_date date NOT NULL DEFAULT CURRENT_DATE;