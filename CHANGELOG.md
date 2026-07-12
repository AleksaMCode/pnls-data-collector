# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New `stats` service for publishing daily and aggregate statistics from the home PostgreSQL source to Supabase, including models, migrations, and initial backfill tooling. PR #337
- New `stats_api` FastAPI service with Supabase-backed endpoints for totals, device stats, manufacturer data, Sankey data, and paginated SSID statistics. PR #337
- Firebase Bearer-token authentication middleware (`FIREBASE_CREDENTIALS_JSON`) and Redis response caching support were added to `stats_api`. PR #337
- New Supabase tables and pipelines for privacy-preserving MAC analytics (`mac_stats` with HMAC hashing) and daily unique snapshots (`unique_total_stats`). This will not be used as MAC table has been removed from Supabase due to memory limits. PR #337
- New monitor dashboard SSID page with server-side pagination/sorting/search and debounced query input. PR #337
- New  FastAPI Cloud deploy workflow for `stats_api`. PR #337

### Changed

- `monitor_dashboard` historical/statistical reads were migrated from Firebase Realtime Database to `stats_api`, while live probe updates remain on Firebase. PR #337
- Frontend API consumption was refactored to a shared authenticated GET client with Firebase ID-token injection and in-flight request de-duplication. PR #337
- Orchestrator DAG flow now calls the `stats` service after `aggregator`, with configurable base URL and timeout settings. PR #337
- Manufacturer and Sankey sections in the dashboard were optimized with lazy loading so expensive data loads only after card expansion. PR #337

### Fixed

- Manufacturer world-map coloring now correctly uses ISO alpha-3 country codes from API responses instead of full country names. PR #337
- Device status rendering in the dashboard grid now refreshes when online-status data updates, preventing stale `Offline` states. PR #337
- Python test workflow discovery was scoped to the `tests/` directory to avoid importing runtime-only packages during CI collection. PR #337

## [2.0.0] - 2026-07-12

### Added

- Sentry fatal-error logging integrated into the Go notifier services: `cloudflare_limit_notifier`, `collector_status_notifier`, and `firebase_limit_notifier`. PR #296
- Mattermost bot icon support added for Go services through service-name-based icon mapping, with custom bot icon assets under `resources/bot_icons/`. PR #296
- Datadog heartbeat status validation added to `collector_status_notifier` as the primary device-health source, with periodic checks and Datadog API integration for configured devices. PR #302
- New `FIREBASE_MONGO_BACKUP_ENABLED` usage flag added to `firebase_housekeeping` to control MongoDB backup behavior during cleanup workflows. PR #301
- `db_backup` workflow now includes `cleanup_local_files_task`, which deletes local temporary backup artifacts after successful upload. PR #307
- Internal Sentry fatal logging was added to `db_backup` via `internal/logging`, configurable through `SENTRY_DSN` and `SERVICE_NAME`. PR #307
- Aggregator now sends a Mattermost message when the workflow starts. PR #308
- New `home_server_limit_notifier` Go microservice added to monitor host SSD usage and send Mattermost reports on-demand via an HTTP trigger endpoint. PR #312
- New `orchestrator` added that now governs `aggregate`, `firebase_housekeeping` and `db_backup` services. Backup is now triggered after the main aggregation/housekeeping flow. PR #319
  - `aggregate` service restrucered to be an API with Celery worker that governs the import process.
- Added Datadog dashboard snapshot export for device monitoring, including home server visibility updates under `collector_metrics_agent/datadog/dashboard_snapshots/`. PR #333
- Redis-backed lookup cache helpers were added for SSID/MAC ID resolution in `aggregator` with a 1-hour TTL. PR #335

### Changed

- Changed Firebase cleanup to use batch-delete workflow. PR #267
- Firebase cleanup batch-delete flow now skips nodes for the current day to avoid removing fresh data. PR #267
- Go formatter automation updated to include a previously missing service target. PR #284
- README documentation updated and refined across multiple passes (wording, spelling, and clarity improvements).
- `collector_status_notifier` now performs device status checks every 5 minutes via Datadog and falls back to Firebase status checks when Datadog is unavailable. PR #302
- `firebase_housekeeping` logging was expanded with additional runtime messages for better operational visibility.
- Aggregator `/aggregate` endpoint now behaves idempotently for concurrent triggers by returning the already running workflow id instead of creating a duplicate active workflow. PR #319
- `collector` capture scheduling now supports a `CAPTURE_24_7` configuration flag to allow continuous capture outside working-hours windows. PR #319
- Dashboard live-toggle condition was updated to support always-live operation. PR #327
- `collector_metrics_agent` dependency manifests were updated and the settings template filename typo was fixed (`settings.py.template.py` -> `settings.py.template`). PR #333
- Aggregator stats publishing now accepts an optional import date and uses it when publishing daily stats, so day-after imports publish daily aggregates for the imported day instead of only for today. PR #335
- Aggregator import lookup flow now resolves SSID and MAC IDs through dedicated helpers instead of preloading full SSID/MAC tables into memory before import.
- Aggregator now stores initial workflow `STARTED` status in Redis with a 5-hour TTL to reduce stale in-progress status keys after unexpected worker shutdowns.
- Invalid-channel skip logging during import was lowered from warning to info to reduce noisy alerting.

### Fixed

- `db_backup` Conductor Docker healthcheck endpoint was corrected from `/api/health` to `/health`, resolving false `unhealthy` container status after worker runs.
- `orchestrator` db backup trigger now accepts both JSON and plain-text Conductor workflow id responses (including `raw_response` fallback), preventing false "missing workflow id" failures. PR #319
- `db_backup` upload pipeline and worker now emit detailed runtime diagnostics (input validation, file size/path, object key, elapsed time, and upload errors) to improve R2 upload troubleshooting. PR #324
- `db_backup` upload timeout handling was improved for backup artifact transfers to R2. PR #324
- `monitor_dashboard` live Probe Request card no longer spikes to an incorrect percentage on first live update due to stale-state percentage calculation. PR #327
- `collector` and `aggregator` now validate channel values before persistence, preventing invalid channel IDs (e.g., `124`) from causing `captured_info_channel_fkey` foreign key failures during import. PR #329
- `aggregator` service restart policy was updated to `unless-stopped` in Docker Compose. PR #331

## [1.0.0] - 2026-05-30

### Added

- Public stable release of the PNLS-DC distributed data collection platform.
- Distributed edge `collector` service for Wi-Fi probe request capture with preprocessing and encryption before ingestion.
- Event-driven ingestion layer on Firebase Realtime Database for real-time capture workflows.
- Daily batch ETL (`aggregator`) into PostgreSQL with decryption, transformation, loading, and daily statistics publishing.
- Operational maintenance services:
  - `firebase_housekeeping` for periodic Firebase cleanup and MongoDB archival.
  - `collector_status_notifier` for device availability checks and alerting.
  - `firebase_limit_notifier` and `cloudflare_limit_notifier` for usage tracking and quota safety.
  - `collector_metrics_agent` for edge device metrics collection and Datadog reporting.
- PostgreSQL analytics storage and migration workflow for structured research data.
- `db_backup` workflow for automated PostgreSQL backup, encryption, compression, and Cloudflare R2 upload.
- `monitor_dashboard` frontend for authenticated monitoring, real-time updates, and analytics visualization.
- Centralized observability and alerting integrations with Sentry and Mattermost-compatible channels.

### Changed

- Collector pipeline improvements and throughput optimizations, including channel hopping, filtering, parser refactors, and concurrency fixes.
- Data model and ETL updates to support Wi-Fi channel capture in downstream analytics.
- Reliability and deployment hardening across microservices through test, pipeline, and runtime fixes.
- UI quality improvements in dashboard components for better data readability.
- Documentation expanded in `README.md` with architecture overview, deployment notes, and operational context for the public release.

### Fixed

- Multiple bug fixes across collector, aggregator, dashboard, and metrics-agent workflows to improve production stability.
- Import/runtime issues, CI formatting checks, and service-level regressions identified during pre-release stabilization.

