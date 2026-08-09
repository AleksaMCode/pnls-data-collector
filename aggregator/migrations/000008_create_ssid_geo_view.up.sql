CREATE VIEW public.ssid_geo_reduced_resolved AS
SELECT
    sgr.id,
    s.ssid AS ssid,
    sgr.latitude,
    sgr.longitude,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    sgr.created_date
FROM public.ssid_geo_reduced sgr
JOIN public.ssid s ON s.id = sgr.ssid
LEFT JOIN public.country c ON c.id = sgr.country
ORDER BY sgr.id;
