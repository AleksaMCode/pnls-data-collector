-- Clean up duplicate imports - this keeps the row with the lower id (the first import id)
DELETE FROM captured_info c
USING (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY ssid, mac, location, "timestamp"
                   ORDER BY id ASC
               ) AS rn
        FROM captured_info
        WHERE "timestamp" >= CURRENT_DATE
          AND "timestamp" < CURRENT_DATE + INTERVAL '1 day'
    ) t
    WHERE rn > 1
) d
WHERE c.id = d.id;

-- Clean up duplicate imports - this keeps the row with the highest id
DELETE FROM imports_info
WHERE id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY "timestamp", captured
                   ORDER BY id DESC
               ) AS rn
        FROM imports_info
    ) t
    WHERE rn > 1
);