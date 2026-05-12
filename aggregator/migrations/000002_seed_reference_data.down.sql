DELETE FROM location_mapping
WHERE device IN ('RPI-1', 'RPI-2', 'RPI-3');

DELETE FROM location
WHERE location IN ('61/R-202', '62/R-001', '31/R-009');