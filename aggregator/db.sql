CREATE DATABASE PNLS;

-- Connect to PNLS
\c PNLS;

CREATE TABLE SSID (
    id SERIAL PRIMARY KEY,
    ssid VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE MAC (
    id SERIAL PRIMARY KEY,
    mac VARCHAR(17) UNIQUE NOT NULL  -- mac format: XX:XX:XX:XX:XX:XX
);

CREATE TABLE LOCATION (
    id SERIAL PRIMARY KEY,
    location VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255) NOT NULL
);

INSERT INTO LOCATION (location, description) VALUES
('61/R-202', 'Users Office''s waiting room'),
('62/R-001', 'CERN Community Support Centre'),
('31/R-009', 'Stefan''s office');

CREATE TABLE IMPORTS_INFO (
    id SERIAL PRIMARY KEY,
    timestamp DATE NOT NULL DEFAULT '2025-10-30'
);

INSERT INTO IMPORTS_INFO DEFAULT VALUES;

CREATE TABLE CAPTURED_INFO (
    id SERIAL PRIMARY KEY,
    ssid INT NOT NULL REFERENCES SSID(id),
    mac INT NOT NULL REFERENCES MAC(id),
    location INT NOT NULL REFERENCES LOCATION(id),
    timestamp TIMESTAMP NOT NULL,
    UNIQUE(ssid, mac, location)
);

CREATE VIEW captured_info_resolved AS
SELECT
    c.id,
    s.ssid AS ssid,
    m.mac AS mac,
    l.location || ' - ' || l.description AS location,
    c.timestamp
FROM CAPTURED_INFO c
JOIN SSID s ON c.ssid = s.id
JOIN MAC m ON c.mac = m.id
JOIN LOCATION l ON c.location = l.id;

CREATE TABLE location_mapping (
    id SERIAL PRIMARY KEY,
    device VARCHAR(50) UNIQUE NOT NULL,
    location_id INTEGER NOT NULL REFERENCES location(id)
);

INSERT INTO location_mapping (device, location_id) VALUES
('RPI-1', 1),
('RPI-2', 2),
('RPI-3', 3);

ALTER TABLE captured_info
ADD CONSTRAINT unique_captured
UNIQUE (ssid, mac, location, timestamp);

ALTER TABLE captured_info
DROP CONSTRAINT captured_info_ssid_mac_location_key;

ALTER TABLE captured_info
DROP CONSTRAINT unique_captured;

CREATE VIEW location_mapping_resolved AS
SELECT
    lm.device AS device,
    CONCAT(l.location, ' - ', l.description) AS location
FROM location_mapping lm
JOIN location l ON lm.location_id = l.id
ORDER BY lm.device;

ALTER TABLE imports_info
ADD COLUMN captured INTEGER DEFAULT 0;

-- This is uber specific view for CERN Computer Sec Team (not needed otherwise).
CREATE VIEW public.latest_mac_info_for_cern_like_ssid AS
WITH RankedEntries AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY ssid, mac, location ORDER BY timestamp DESC) AS rn
  FROM public.captured_info_resolved
  WHERE ssid ILIKE '%CERN%'
    AND ssid NOT IN ('CERN', 'CERN-Visitors', 'CERN-Campus', 'cern')
)
SELECT ssid, mac, location, timestamp
FROM RankedEntries
WHERE rn = 1;

CREATE VIEW daily_captured_counts AS
SELECT DATE(timestamp) AS day, COUNT(*) AS captured_count
FROM captured_info
GROUP BY day
ORDER BY day;

CREATE VIEW daily_captured_per_device AS
SELECT
    DATE(c.timestamp) AS date,
    lm.device AS device,
    COUNT(DISTINCT s.ssid) AS ssid,
    COUNT(DISTINCT m.mac) AS mac,
    -- count ssid or mac (number is the same) = the count is number of probe requests
	COUNT(s.ssid) AS probe_request
FROM CAPTURED_INFO c
JOIN SSID s
    ON c.ssid = s.id
JOIN MAC m
    ON c.mac = m.id
JOIN LOCATION_MAPPING lm
    ON c.location = lm.location_id
GROUP BY
    DATE(c.timestamp),
    lm.device
ORDER BY
    date,
    device;

-- Add UAA column to MAC table
-- BOOLEAN defaults to nullable
ALTER TABLE public.mac
ADD COLUMN uaa BOOLEAN;

-- Backfill existing rows
UPDATE mac
SET uaa = (
    (('x' || split_part(mac, ':', 1))::bit(8)::int & 2) = 0
);

-- Create a view for the "real" MAC addresses
CREATE VIEW public.mac_uaa AS
SELECT *
FROM public.mac
WHERE uaa IS DISTINCT FROM FALSE
ORDER BY id ASC;
