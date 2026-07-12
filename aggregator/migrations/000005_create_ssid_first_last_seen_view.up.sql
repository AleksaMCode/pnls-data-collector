CREATE VIEW public.ssid_first_last_seen AS
SELECT
    s.ssid AS ssid,
    COUNT(*) AS seen_count,
    MIN(c."timestamp") AS first_seen,
    MAX(c."timestamp") AS last_seen
FROM public.captured_info c
JOIN public.ssid s ON s.id = c.ssid
GROUP BY s.ssid
ORDER BY s.ssid;
