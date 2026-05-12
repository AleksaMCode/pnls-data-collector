INSERT INTO location (location, description)
VALUES
('61/R-202', 'Users Office''s waiting room'),
('62/R-001', 'CERN Community Support Centre'),
('31/R-009', 'Stefan''s office')
ON CONFLICT (location) DO UPDATE
SET description = EXCLUDED.description;

INSERT INTO location_mapping (device, location_id)
VALUES
('RPI-1', (SELECT id FROM location WHERE location = '61/R-202')),
('RPI-2', (SELECT id FROM location WHERE location = '62/R-001')),
('RPI-3', (SELECT id FROM location WHERE location = '31/R-009'))
ON CONFLICT (device) DO UPDATE
SET location_id = EXCLUDED.location_id;

UPDATE location
SET
    latitude = 46.23257940351152,
    longitude = 6.045154364603783
WHERE location = '31/R-009';

UPDATE location
SET
    latitude = 46.231364501742455,
    longitude = 6.054017985878448
WHERE location = '62/R-001';

UPDATE location
SET
    latitude = 46.231551592583266,
    longitude = 6.054826626521773
WHERE location = '61/R-202';

-- Backfill existing rows
UPDATE mac
SET uaa = (
    (('x' || split_part(mac, ':', 1))::bit(8)::int & 2) = 0
);