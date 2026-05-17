-- Legacy pre-migrate schema script; not used by migrate.

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

-- This is uber specific view for CERN Computer Sec Team (not needed otherwise). #31
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

-- Add Country table

CREATE TABLE COUNTRY (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    alpha2 CHAR(2) NOT NULL UNIQUE,
    alpha3 CHAR(3) NOT NULL UNIQUE,
    country_code CHAR(3) NOT NULL UNIQUE,
    region TEXT,
    sub_region TEXT,
    intermediate_region TEXT,
    region_code INT,
    sub_region_code INT,
    intermediate_region_code INT
);

-- Add IEEE OUI
CREATE TABLE IEEE_MAC_OUI_ORG (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    country INT REFERENCES COUNTRY(id)
);

CREATE TABLE IEEE_MAC_OUI (
    id SERIAL PRIMARY KEY,
    registry TEXT NOT NULL,
    assignment TEXT NOT NULL,
    org INT NOT NULL REFERENCES IEEE_MAC_OUI_ORG(id)
);

-- Create a materialized view for OUI
CREATE MATERIALIZED VIEW ieee_mac_oui_with_country AS
SELECT
    oui.id,
    oui.registry,
    oui.assignment,
    org.name AS org,
    c.name AS country
FROM IEEE_MAC_OUI oui
JOIN IEEE_MAC_OUI_ORG org
    ON oui.org = org.id
LEFT JOIN COUNTRY c
    ON org.country = c.id;

-- Some extra indexes

CREATE INDEX idx_mac_oui_assignment
ON IEEE_MAC_OUI (assignment);

CREATE INDEX idx_mac_oui_registry
ON IEEE_MAC_OUI (registry);

CREATE INDEX idx_country
ON country (alpha2);

CREATE INDEX idx_ssid_name
ON SSID (ssid);

CREATE INDEX idx_ieee_mac_oui_registry_assignment
ON ieee_mac_oui (registry, assignment);

-- Add FK to IEEE OUI
ALTER TABLE mac
ADD COLUMN oui INTEGER;

ALTER TABLE mac
ADD CONSTRAINT fk_mac_oui
FOREIGN KEY (oui)
REFERENCES ieee_mac_oui (id);

CREATE INDEX idx_ieee_mac_oui_view_registry_assignment
ON ieee_mac_oui_with_country (registry, assignment);

CREATE VIEW mac_with_org_resolved AS
SELECT
	m.id,
    m.mac,
    m.uaa,
    org.name AS company,
    c.name AS country,
    COUNT(ci.id) AS seen_count
FROM mac m
LEFT JOIN ieee_mac_oui oui
    ON m.oui = oui.id
LEFT JOIN ieee_mac_oui_org org
    ON oui.org = org.id
LEFT JOIN country c
    ON org.country = c.id
LEFT JOIN captured_info ci
    ON ci.mac = m.id
WHERE m.uaa = TRUE
  AND org.name IS NOT NULL
GROUP BY m.id, m.mac, m.uaa, org.name, c.name
ORDER BY seen_count DESC;

CREATE VIEW company_capture_summary AS
SELECT
    org.name AS company,
    c.name AS country,
    COUNT(ci.id) AS total_occurrences
FROM mac m
JOIN captured_info ci
    ON ci.mac = m.id
JOIN ieee_mac_oui oui
    ON m.oui = oui.id
JOIN ieee_mac_oui_org org
    ON oui.org = org.id
LEFT JOIN country c
    ON org.country = c.id
WHERE m.uaa = TRUE
GROUP BY org.name, c.name
ORDER BY total_occurrences DESC;

-- To get count of total Probe Requests with "real" MAC addresses:
SELECT SUM(seen_count) AS total_mac_occurrences
FROM mac_with_org_resolved;

-- GEO mapping changes (#208)
ALTER TABLE SSID
ADD mapped BOOLEAN DEFAULT FALSE;
ADD has_geo BOOLEAN DEFAULT FALSE;

CREATE TABLE SSID_GEO (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ssid INTEGER NOT NULL REFERENCES SSID(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    country INTEGER REFERENCES COUNTRY(id) ON DELETE SET NULL
);

CREATE TABLE SSID_GEO_REDUCED (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ssid INTEGER NOT NULL REFERENCES SSID(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    country INTEGER REFERENCES COUNTRY(id) ON DELETE SET NULL
);

-- View for #215 - show wildcard SSIDs
CREATE OR REPLACE VIEW daily_ssid_counts AS
WITH wildcard_id AS (
    SELECT id AS wildcard_ssid_id
    FROM ssid
    WHERE ssid = '*'
    LIMIT 1
)
SELECT
    DATE(c.timestamp) AS day,
    COUNT(*) AS total_count,
    COUNT(*) FILTER (WHERE c.ssid = w.wildcard_ssid_id) AS wildcard_ssid,
    COUNT(*) FILTER (WHERE c.ssid <> w.wildcard_ssid_id) AS real_ssid,
    CASE
        WHEN COUNT(*) FILTER (WHERE c.ssid <> w.wildcard_ssid_id) = 0
        THEN NULL
        ELSE ROUND(
            (
                COUNT(*) FILTER (WHERE c.ssid = w.wildcard_ssid_id)
                - COUNT(*) FILTER (WHERE c.ssid <> w.wildcard_ssid_id)
            ) * 100.0
            / COUNT(*) FILTER (WHERE c.ssid <> w.wildcard_ssid_id), 2
        )
    END AS wildcard_vs_real_pct
FROM captured_info c
CROSS JOIN wildcard_id w
WHERE c.timestamp >= '2026-03-26 00:00:00+00'
GROUP BY DATE(c.timestamp)
ORDER BY DATE(c.timestamp);


-- Update CERN view #227
CREATE OR REPLACE VIEW public.latest_mac_info_for_cern_like_ssid AS
WITH RankedEntries AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY ssid, mac, location ORDER BY timestamp DESC) AS rn
  FROM public.captured_info_resolved
  WHERE ssid ILIKE '%CERN%'
    AND ssid NOT IN ('CERN', 'CERN-Visitors', 'CERN-Campus', 'cern', ' CERN-Visitors')
)
SELECT ssid, mac, location, timestamp
FROM RankedEntries
WHERE rn = 1;

-- Update the view of device's manufacturer
DROP VIEW company_capture_summary;
CREATE VIEW company_capture_summary AS
SELECT
    org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    COUNT(ci.id) AS total_occurrences,
    ROUND(
        100.0 * COUNT(ci.id) / SUM(COUNT(ci.id)) OVER (),
        4
    ) AS percentage
FROM mac m
JOIN captured_info ci
    ON ci.mac = m.id
JOIN ieee_mac_oui oui
    ON m.oui = oui.id
JOIN ieee_mac_oui_org org
    ON oui.org = org.id
LEFT JOIN country c
    ON org.country = c.id
WHERE m.uaa = TRUE
GROUP BY org.name, c.name, c.alpha3
ORDER BY total_occurrences DESC;

CREATE OR REPLACE VIEW company_capture_summary_by_device AS
SELECT
    lm.device AS device,
    org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    COUNT(ci.id) AS total_occurrences,
    ROUND(
        100.0 * COUNT(ci.id) / SUM(COUNT(ci.id)) OVER (PARTITION BY lm.device),
        4
    ) AS percentage
FROM mac m
JOIN captured_info ci
    ON ci.mac = m.id
JOIN location_mapping lm
    ON ci.location = lm.location_id
JOIN ieee_mac_oui oui
    ON m.oui = oui.id
JOIN ieee_mac_oui_org org
    ON oui.org = org.id
LEFT JOIN country c
    ON org.country = c.id
WHERE
    m.uaa = TRUE
GROUP BY lm.device, org.name, c.name, c.alpha3
ORDER BY lm.device, total_occurrences DESC;

ALTER TABLE location
ADD COLUMN latitude DOUBLE PRECISION,
ADD COLUMN longitude DOUBLE PRECISION;

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

CREATE OR REPLACE VIEW location_mapping_resolved AS
SELECT
    lm.device AS device,
    CONCAT(l.description, ' (', l.location, ')') AS location,
    CASE
        WHEN l.latitude IS NULL OR l.longitude IS NULL THEN NULL
        ELSE CONCAT(l.latitude, ',', l.longitude)
    END AS coordinates
FROM location_mapping lm
JOIN location l ON lm.location_id = l.id
ORDER BY lm.device;

-- Performance boost to daily_captured_per_device #246
-- Original time was about 40 seconds, after optimization it was about 19 seconds
-- Add a generated column for the date
ALTER TABLE captured_info
ADD COLUMN capture_date DATE GENERATED ALWAYS AS (DATE(timestamp)) STORED;

-- Index it
CREATE INDEX idx_captured_info_capture_date ON captured_info(capture_date);

DROP VIEW daily_captured_per_device;
CREATE VIEW daily_captured_per_device AS
SELECT
    c.capture_date AS date,
    lm.device AS device,
    COUNT(DISTINCT c.ssid) AS ssid,
    COUNT(DISTINCT c.mac) AS mac,
    COUNT(c.ssid) AS probe_request
FROM captured_info c
JOIN location_mapping lm
    ON c.location = lm.location_id
GROUP BY
    c.capture_date,
    lm.device
ORDER BY
    date,
    device;

CREATE OR REPLACE VIEW total_captured_per_device AS
SELECT
  device,
  SUM(ssid)::BIGINT AS ssid,
  SUM(mac)::BIGINT AS mac,
  SUM(probe_request)::BIGINT AS probe_request
FROM daily_captured_per_device
GROUP BY device
ORDER BY device;

CREATE TABLE channels_2_4_wifi (
    id SERIAL PRIMARY KEY,
    channel_number INT NOT NULL,
    lower_frequency INT NOT NULL,
    center_frequency INT NOT NULL,
    upper_frequency INT NOT NULL
);

INSERT INTO channels_2_4_wifi (
    channel_number,
    lower_frequency,
    center_frequency,
    upper_frequency
) VALUES
(1, 2401, 2412, 2423),
(2, 2406, 2417, 2428),
(3, 2411, 2422, 2433),
(4, 2416, 2427, 2438),
(5, 2421, 2432, 2443),
(6, 2426, 2437, 2448),
(7, 2431, 2442, 2453),
(8, 2436, 2447, 2458),
(9, 2441, 2452, 2463),
(10, 2446, 2457, 2468),
(11, 2451, 2462, 2473),
(12, 2456, 2467, 2478),
(13, 2461, 2472, 2483),
(14, 2473, 2484, 2495);

-- Using default value 10 for channels as all of the RPI devices capture on that channel.
-- Default data is done for the old data, the new data will have its channel set.
ALTER TABLE captured_info
ADD COLUMN channel INTEGER NOT NULL DEFAULT 10 REFERENCES channels_2_4_wifi(id);