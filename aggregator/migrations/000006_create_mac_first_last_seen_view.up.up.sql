CREATE VIEW public.mac_first_last_seen AS
SELECT
    m.mac AS mac,
    COUNT(*) AS seen_count,
    MIN(c."timestamp") AS first_seen,
    MAX(c."timestamp") AS last_seen
FROM public.captured_info c
JOIN public.mac m ON m.id = c.mac
GROUP BY m.mac
ORDER BY m.mac;
