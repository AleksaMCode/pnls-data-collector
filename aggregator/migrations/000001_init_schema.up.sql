--
-- Name: captured_info; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.captured_info (
    id integer NOT NULL,
    ssid integer NOT NULL,
    mac integer NOT NULL,
    location integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    capture_date date GENERATED ALWAYS AS (date("timestamp")) STORED,
    channel integer DEFAULT 10 NOT NULL
);


--
-- Name: captured_info_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.captured_info_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: captured_info_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.captured_info_id_seq OWNED BY public.captured_info.id;


--
-- Name: location; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.location (
    id integer NOT NULL,
    location character varying(50) NOT NULL,
    description character varying(255) NOT NULL,
    latitude double precision,
    longitude double precision
);


--
-- Name: mac; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mac (
    id integer NOT NULL,
    mac character varying(17) NOT NULL,
    uaa boolean,
    oui integer
);


--
-- Name: ssid; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ssid (
    id integer NOT NULL,
    ssid character varying(255) NOT NULL,
    mapped boolean DEFAULT false,
    has_geo boolean DEFAULT false
);


--
-- Name: captured_info_resolved; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.captured_info_resolved AS
 SELECT c.id,
    s.ssid,
    m.mac,
    (((l.location)::text || ' - '::text) || (l.description)::text) AS location,
    c."timestamp"
   FROM (((public.captured_info c
     JOIN public.ssid s ON ((c.ssid = s.id)))
     JOIN public.mac m ON ((c.mac = m.id)))
     JOIN public.location l ON ((c.location = l.id)));


--
-- Name: channels_2_4_wifi; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channels_2_4_wifi (
    id integer NOT NULL,
    channel_number integer NOT NULL,
    lower_frequency integer NOT NULL,
    center_frequency integer NOT NULL,
    upper_frequency integer NOT NULL
);


--
-- Name: channels_2_4_wifi_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.channels_2_4_wifi_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: channels_2_4_wifi_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.channels_2_4_wifi_id_seq OWNED BY public.channels_2_4_wifi.id;


--
-- Name: country; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.country (
    id integer NOT NULL,
    name text NOT NULL,
    alpha2 character(2) NOT NULL,
    alpha3 character(3) NOT NULL,
    country_code character(3) NOT NULL,
    region text,
    sub_region text,
    intermediate_region text,
    region_code integer,
    sub_region_code integer,
    intermediate_region_code integer
);


--
-- Name: ieee_mac_oui; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ieee_mac_oui (
    id integer NOT NULL,
    registry text NOT NULL,
    assignment text NOT NULL,
    org integer NOT NULL
);


--
-- Name: ieee_mac_oui_org; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ieee_mac_oui_org (
    id integer NOT NULL,
    name text NOT NULL,
    address text,
    country integer
);


--
-- Name: company_capture_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.company_capture_summary AS
 SELECT org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    count(ci.id) AS total_occurrences,
    round(((100.0 * (count(ci.id))::numeric) / sum(count(ci.id)) OVER ()), 4) AS percentage
   FROM ((((public.mac m
     JOIN public.captured_info ci ON ((ci.mac = m.id)))
     JOIN public.ieee_mac_oui oui ON ((m.oui = oui.id)))
     JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
  WHERE (m.uaa = true)
  GROUP BY org.name, c.name, c.alpha3
  ORDER BY (count(ci.id)) DESC;


--
-- Name: location_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.location_mapping (
    id integer NOT NULL,
    device character varying(50) NOT NULL,
    location_id integer NOT NULL
);


--
-- Name: company_capture_summary_by_device; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.company_capture_summary_by_device AS
 SELECT lm.device,
    org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    count(ci.id) AS total_occurrences,
    round(((100.0 * (count(ci.id))::numeric) / sum(count(ci.id)) OVER (PARTITION BY lm.device)), 4) AS percentage
   FROM (((((public.mac m
     JOIN public.captured_info ci ON ((ci.mac = m.id)))
     JOIN public.location_mapping lm ON ((ci.location = lm.location_id)))
     JOIN public.ieee_mac_oui oui ON ((m.oui = oui.id)))
     JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
  WHERE (m.uaa = true)
  GROUP BY lm.device, org.name, c.name, c.alpha3
  ORDER BY lm.device, (count(ci.id)) DESC;


--
-- Name: company_capture_summary_rpi1; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.company_capture_summary_rpi1 AS
 SELECT org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    count(ci.id) AS total_occurrences,
    round(((100.0 * (count(ci.id))::numeric) / sum(count(ci.id)) OVER ()), 4) AS percentage
   FROM (((((public.mac m
     JOIN public.captured_info ci ON ((ci.mac = m.id)))
     JOIN public.location_mapping lm ON ((ci.location = lm.location_id)))
     JOIN public.ieee_mac_oui oui ON ((m.oui = oui.id)))
     JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
  WHERE ((m.uaa = true) AND ((lm.device)::text = 'RPI-1'::text))
  GROUP BY org.name, c.name, c.alpha3
  ORDER BY (count(ci.id)) DESC;


--
-- Name: company_capture_summary_rpi2; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.company_capture_summary_rpi2 AS
 SELECT org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    count(ci.id) AS total_occurrences,
    round(((100.0 * (count(ci.id))::numeric) / sum(count(ci.id)) OVER ()), 4) AS percentage
   FROM (((((public.mac m
     JOIN public.captured_info ci ON ((ci.mac = m.id)))
     JOIN public.location_mapping lm ON ((ci.location = lm.location_id)))
     JOIN public.ieee_mac_oui oui ON ((m.oui = oui.id)))
     JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
  WHERE ((m.uaa = true) AND ((lm.device)::text = 'RPI-2'::text))
  GROUP BY org.name, c.name, c.alpha3
  ORDER BY (count(ci.id)) DESC;


--
-- Name: company_capture_summary_rpi3; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.company_capture_summary_rpi3 AS
 SELECT org.name AS company,
    c.name AS country,
    c.alpha3 AS country_alpha3,
    count(ci.id) AS total_occurrences,
    round(((100.0 * (count(ci.id))::numeric) / sum(count(ci.id)) OVER ()), 4) AS percentage
   FROM (((((public.mac m
     JOIN public.captured_info ci ON ((ci.mac = m.id)))
     JOIN public.location_mapping lm ON ((ci.location = lm.location_id)))
     JOIN public.ieee_mac_oui oui ON ((m.oui = oui.id)))
     JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
  WHERE ((m.uaa = true) AND ((lm.device)::text = 'RPI-3'::text))
  GROUP BY org.name, c.name, c.alpha3
  ORDER BY (count(ci.id)) DESC;


--
-- Name: country_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.country_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: country_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.country_id_seq OWNED BY public.country.id;


--
-- Name: daily_captured_counts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.daily_captured_counts AS
 SELECT date("timestamp") AS day,
    count(*) AS captured_count
   FROM public.captured_info
  GROUP BY (date("timestamp"))
  ORDER BY (date("timestamp"));


--
-- Name: daily_captured_per_device; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.daily_captured_per_device AS
 SELECT c.capture_date AS date,
    lm.device,
    count(DISTINCT c.ssid) AS ssid,
    count(DISTINCT c.mac) AS mac,
    count(c.ssid) AS probe_request
   FROM (public.captured_info c
     JOIN public.location_mapping lm ON ((c.location = lm.location_id)))
  GROUP BY c.capture_date, lm.device
  ORDER BY c.capture_date, lm.device;


--
-- Name: daily_ssid_counts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.daily_ssid_counts AS
 WITH wildcard_id AS (
         SELECT ssid.id AS wildcard_ssid_id
           FROM public.ssid
          WHERE ((ssid.ssid)::text = '*'::text)
         LIMIT 1
        )
 SELECT date(c."timestamp") AS day,
    count(*) AS total_count,
    count(*) FILTER (WHERE (c.ssid = w.wildcard_ssid_id)) AS wildcard_ssid,
    count(*) FILTER (WHERE (c.ssid <> w.wildcard_ssid_id)) AS real_ssid,
        CASE
            WHEN (count(*) FILTER (WHERE (c.ssid <> w.wildcard_ssid_id)) = 0) THEN NULL::numeric
            ELSE round(((((count(*) FILTER (WHERE (c.ssid = w.wildcard_ssid_id)) - count(*) FILTER (WHERE (c.ssid <> w.wildcard_ssid_id))))::numeric * 100.0) / (count(*) FILTER (WHERE (c.ssid <> w.wildcard_ssid_id)))::numeric), 2)
        END AS wildcard_vs_real_pct
   FROM (public.captured_info c
     CROSS JOIN wildcard_id w)
  WHERE (c."timestamp" >= '2026-03-26 00:00:00'::timestamp without time zone)
  GROUP BY (date(c."timestamp"))
  ORDER BY (date(c."timestamp"));


--
-- Name: ieee_mac_oui_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ieee_mac_oui_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ieee_mac_oui_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ieee_mac_oui_id_seq OWNED BY public.ieee_mac_oui.id;


--
-- Name: ieee_mac_oui_org_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ieee_mac_oui_org_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ieee_mac_oui_org_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ieee_mac_oui_org_id_seq OWNED BY public.ieee_mac_oui_org.id;


--
-- Name: ieee_mac_oui_with_country; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.ieee_mac_oui_with_country AS
 SELECT oui.id,
    oui.registry,
    oui.assignment,
    org.name AS org,
    c.name AS country
   FROM ((public.ieee_mac_oui oui
     JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
  WITH NO DATA;


--
-- Name: imports_info; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.imports_info (
    id integer NOT NULL,
    "timestamp" date DEFAULT '2025-10-30'::date NOT NULL,
    captured integer DEFAULT 0
);


--
-- Name: imports_info_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.imports_info_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: imports_info_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.imports_info_id_seq OWNED BY public.imports_info.id;


--
-- Name: latest_mac_info_for_cern_like_ssid; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.latest_mac_info_for_cern_like_ssid AS
 WITH rankedentries AS (
         SELECT captured_info_resolved.id,
            captured_info_resolved.ssid,
            captured_info_resolved.mac,
            captured_info_resolved.location,
            captured_info_resolved."timestamp",
            row_number() OVER (PARTITION BY captured_info_resolved.ssid, captured_info_resolved.mac, captured_info_resolved.location ORDER BY captured_info_resolved."timestamp" DESC) AS rn
           FROM public.captured_info_resolved
          WHERE (((captured_info_resolved.ssid)::text ~~* '%CERN%'::text) AND ((captured_info_resolved.ssid)::text <> ALL ((ARRAY['CERN'::character varying, 'CERN-Visitors'::character varying, 'CERN-Campus'::character varying, 'cern'::character varying, ' CERN-Visitors'::character varying])::text[])))
        )
 SELECT ssid,
    mac,
    location,
    "timestamp"
   FROM rankedentries
  WHERE (rn = 1);


--
-- Name: location_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.location_id_seq OWNED BY public.location.id;


--
-- Name: location_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.location_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: location_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.location_mapping_id_seq OWNED BY public.location_mapping.id;


--
-- Name: location_mapping_resolved; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.location_mapping_resolved AS
 SELECT lm.device,
    concat(l.description, ' (', l.location, ')') AS location,
        CASE
            WHEN ((l.latitude IS NULL) OR (l.longitude IS NULL)) THEN NULL::text
            ELSE concat(l.latitude, ',', l.longitude)
        END AS coordinates
   FROM (public.location_mapping lm
     JOIN public.location l ON ((lm.location_id = l.id)))
  ORDER BY lm.device;


--
-- Name: mac_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mac_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mac_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mac_id_seq OWNED BY public.mac.id;


--
-- Name: mac_uaa; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.mac_uaa AS
 SELECT id,
    mac,
    uaa
   FROM public.mac
  WHERE (uaa IS DISTINCT FROM false)
  ORDER BY id;


--
-- Name: mac_with_org_resolved; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.mac_with_org_resolved AS
 SELECT m.id,
    m.mac,
    m.uaa,
    org.name AS company,
    c.name AS country,
    count(ci.id) AS seen_count
   FROM ((((public.mac m
     LEFT JOIN public.ieee_mac_oui oui ON ((m.oui = oui.id)))
     LEFT JOIN public.ieee_mac_oui_org org ON ((oui.org = org.id)))
     LEFT JOIN public.country c ON ((org.country = c.id)))
     LEFT JOIN public.captured_info ci ON ((ci.mac = m.id)))
  WHERE ((m.uaa = true) AND (org.name IS NOT NULL))
  GROUP BY m.id, m.mac, m.uaa, org.name, c.name
  ORDER BY (count(ci.id)) DESC;


--
-- Name: ssid_geo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ssid_geo (
    id integer NOT NULL,
    ssid integer NOT NULL,
    latitude double precision,
    longitude double precision,
    country integer
);


--
-- Name: ssid_geo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ssid_geo ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.ssid_geo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ssid_geo_reduced; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ssid_geo_reduced (
    id integer NOT NULL,
    ssid integer NOT NULL,
    latitude double precision,
    longitude double precision,
    country integer
);


--
-- Name: ssid_geo_reduced_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ssid_geo_reduced ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.ssid_geo_reduced_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ssid_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ssid_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ssid_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ssid_id_seq OWNED BY public.ssid.id;


--
-- Name: total_captured_per_device; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.total_captured_per_device AS
 SELECT device,
    (sum(ssid))::bigint AS ssid,
    (sum(mac))::bigint AS mac,
    (sum(probe_request))::bigint AS probe_request
   FROM public.daily_captured_per_device
  GROUP BY device
  ORDER BY device;


--
-- Name: captured_info id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.captured_info ALTER COLUMN id SET DEFAULT nextval('public.captured_info_id_seq'::regclass);


--
-- Name: channels_2_4_wifi id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels_2_4_wifi ALTER COLUMN id SET DEFAULT nextval('public.channels_2_4_wifi_id_seq'::regclass);


--
-- Name: country id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.country ALTER COLUMN id SET DEFAULT nextval('public.country_id_seq'::regclass);


--
-- Name: ieee_mac_oui id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ieee_mac_oui ALTER COLUMN id SET DEFAULT nextval('public.ieee_mac_oui_id_seq'::regclass);


--
-- Name: ieee_mac_oui_org id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ieee_mac_oui_org ALTER COLUMN id SET DEFAULT nextval('public.ieee_mac_oui_org_id_seq'::regclass);


--
-- Name: imports_info id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.imports_info ALTER COLUMN id SET DEFAULT nextval('public.imports_info_id_seq'::regclass);


--
-- Name: location id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location ALTER COLUMN id SET DEFAULT nextval('public.location_id_seq'::regclass);


--
-- Name: location_mapping id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_mapping ALTER COLUMN id SET DEFAULT nextval('public.location_mapping_id_seq'::regclass);


--
-- Name: mac id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac ALTER COLUMN id SET DEFAULT nextval('public.mac_id_seq'::regclass);


--
-- Name: ssid id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid ALTER COLUMN id SET DEFAULT nextval('public.ssid_id_seq'::regclass);


--
-- Name: captured_info captured_info_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.captured_info
    ADD CONSTRAINT captured_info_pkey PRIMARY KEY (id);


--
-- Name: channels_2_4_wifi channels_2_4_wifi_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channels_2_4_wifi
    ADD CONSTRAINT channels_2_4_wifi_pkey PRIMARY KEY (id);


--
-- Name: country country_alpha2_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.country
    ADD CONSTRAINT country_alpha2_key UNIQUE (alpha2);


--
-- Name: country country_alpha3_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.country
    ADD CONSTRAINT country_alpha3_key UNIQUE (alpha3);


--
-- Name: country country_country_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.country
    ADD CONSTRAINT country_country_code_key UNIQUE (country_code);


--
-- Name: country country_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.country
    ADD CONSTRAINT country_pkey PRIMARY KEY (id);


--
-- Name: ieee_mac_oui_org ieee_mac_oui_org_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ieee_mac_oui_org
    ADD CONSTRAINT ieee_mac_oui_org_pkey PRIMARY KEY (id);


--
-- Name: ieee_mac_oui ieee_mac_oui_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ieee_mac_oui
    ADD CONSTRAINT ieee_mac_oui_pkey PRIMARY KEY (id);


--
-- Name: imports_info imports_info_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.imports_info
    ADD CONSTRAINT imports_info_pkey PRIMARY KEY (id);


--
-- Name: location location_location_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location
    ADD CONSTRAINT location_location_key UNIQUE (location);


--
-- Name: location_mapping location_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_mapping
    ADD CONSTRAINT location_mapping_pkey PRIMARY KEY (id);


--
-- Name: location location_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location
    ADD CONSTRAINT location_pkey PRIMARY KEY (id);


--
-- Name: mac mac_mac_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac
    ADD CONSTRAINT mac_mac_key UNIQUE (mac);


--
-- Name: mac mac_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac
    ADD CONSTRAINT mac_pkey PRIMARY KEY (id);


--
-- Name: ssid_geo ssid_geo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid_geo
    ADD CONSTRAINT ssid_geo_pkey PRIMARY KEY (id);


--
-- Name: ssid_geo_reduced ssid_geo_reduced_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid_geo_reduced
    ADD CONSTRAINT ssid_geo_reduced_pkey PRIMARY KEY (id);


--
-- Name: ssid ssid_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid
    ADD CONSTRAINT ssid_pkey PRIMARY KEY (id);


--
-- Name: ssid ssid_ssid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid
    ADD CONSTRAINT ssid_ssid_key UNIQUE (ssid);


--
-- Name: idx_captured_info_capture_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_captured_info_capture_date ON public.captured_info USING btree (capture_date);


--
-- Name: idx_captured_info_location; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_captured_info_location ON public.captured_info USING btree (location);


--
-- Name: idx_captured_info_mac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_captured_info_mac ON public.captured_info USING btree (mac);


--
-- Name: idx_captured_info_ssid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_captured_info_ssid ON public.captured_info USING btree (ssid);


--
-- Name: idx_captured_info_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_captured_info_timestamp ON public.captured_info USING btree ("timestamp");


--
-- Name: idx_country; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_country ON public.country USING btree (alpha2);


--
-- Name: idx_ieee_mac_oui_registry_assignment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ieee_mac_oui_registry_assignment ON public.ieee_mac_oui USING btree (registry, assignment);


--
-- Name: idx_ieee_mac_oui_view_registry_assignment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ieee_mac_oui_view_registry_assignment ON public.ieee_mac_oui_with_country USING btree (registry, assignment);


--
-- Name: idx_location_mapping_location_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_location_mapping_location_id ON public.location_mapping USING btree (location_id);


--
-- Name: idx_mac_oui_assignment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mac_oui_assignment ON public.ieee_mac_oui USING btree (assignment);


--
-- Name: idx_mac_oui_registry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mac_oui_registry ON public.ieee_mac_oui USING btree (registry);


--
-- Name: idx_ssid_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ssid_name ON public.ssid USING btree (ssid);


--
-- Name: captured_info captured_info_channel_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.captured_info
    ADD CONSTRAINT captured_info_channel_fkey FOREIGN KEY (channel) REFERENCES public.channels_2_4_wifi(id);


--
-- Name: captured_info captured_info_location_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.captured_info
    ADD CONSTRAINT captured_info_location_fkey FOREIGN KEY (location) REFERENCES public.location(id);


--
-- Name: captured_info captured_info_mac_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.captured_info
    ADD CONSTRAINT captured_info_mac_fkey FOREIGN KEY (mac) REFERENCES public.mac(id);


--
-- Name: captured_info captured_info_ssid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.captured_info
    ADD CONSTRAINT captured_info_ssid_fkey FOREIGN KEY (ssid) REFERENCES public.ssid(id);


--
-- Name: mac fk_mac_oui; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mac
    ADD CONSTRAINT fk_mac_oui FOREIGN KEY (oui) REFERENCES public.ieee_mac_oui(id);


--
-- Name: ieee_mac_oui_org ieee_mac_oui_org_country_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ieee_mac_oui_org
    ADD CONSTRAINT ieee_mac_oui_org_country_fkey FOREIGN KEY (country) REFERENCES public.country(id);


--
-- Name: ieee_mac_oui ieee_mac_oui_org_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ieee_mac_oui
    ADD CONSTRAINT ieee_mac_oui_org_fkey FOREIGN KEY (org) REFERENCES public.ieee_mac_oui_org(id);


--
-- Name: location_mapping location_mapping_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.location_mapping
    ADD CONSTRAINT location_mapping_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.location(id);


--
-- Name: ssid_geo ssid_geo_country_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid_geo
    ADD CONSTRAINT ssid_geo_country_fkey FOREIGN KEY (country) REFERENCES public.country(id) ON DELETE SET NULL;


--
-- Name: ssid_geo_reduced ssid_geo_reduced_country_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid_geo_reduced
    ADD CONSTRAINT ssid_geo_reduced_country_fkey FOREIGN KEY (country) REFERENCES public.country(id) ON DELETE SET NULL;


--
-- Name: ssid_geo_reduced ssid_geo_reduced_ssid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid_geo_reduced
    ADD CONSTRAINT ssid_geo_reduced_ssid_fkey FOREIGN KEY (ssid) REFERENCES public.ssid(id) ON DELETE CASCADE;


--
-- Name: ssid_geo ssid_geo_ssid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssid_geo
    ADD CONSTRAINT ssid_geo_ssid_fkey FOREIGN KEY (ssid) REFERENCES public.ssid(id) ON DELETE CASCADE;
