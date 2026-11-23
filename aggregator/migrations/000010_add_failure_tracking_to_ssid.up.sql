ALTER TABLE public.ssid
    ADD COLUMN failed_attempts integer NOT NULL DEFAULT 0,
    ADD COLUMN last_failure_reason character varying(64),
    ADD COLUMN last_attempt_at timestamp with time zone;
