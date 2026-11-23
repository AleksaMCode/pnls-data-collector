ALTER TABLE public.ssid
    DROP COLUMN IF EXISTS last_attempt_at,
    DROP COLUMN IF EXISTS last_failure_reason,
    DROP COLUMN IF EXISTS failed_attempts;
