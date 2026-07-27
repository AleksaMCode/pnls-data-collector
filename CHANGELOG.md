# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.2] - 2026-07-27

### Changed

- `monitor-dashboard` side navigation now supports a foldable desktop mini-rail layout with an inline chevron toggle in the menu header, preserving quick icon-based navigation while collapsed. PR #375

### Fixed

- Dashboard header stacking order was adjusted so the sticky header no longer overlays the side menu during horizontal scroll interactions. PR #375
- Device-grid capturing tooltip was updated to reflect continuous 24/7 capture operation. PR #375

## [3.1.1] - 2026-07-25

### Added

- New public `stats-api` endpoint `GET /health` was added for lightweight service health checks and cold-start warm-up pings. PR #369

### Changed

- `monitor-dashboard` stats API client `apiGet` now supports optional request options (`auth`, `signal`, `cache`), with authenticated Bearer-token usage still enabled by default. PR #369
- New `fetchStatsApiHealth` helper was added to `monitor-dashboard` stats API wrappers to perform unauthenticated health calls through the shared client layer. PR #369
- Login page warm-up behavior now uses a fire-and-forget `GET /health` call through the shared stats API helper to proactively wake `stats-api` during sign-in. PR #369

## [3.1.0] - 2026-07-23

### Added

- New `stats-api` endpoint `GET /stats/average/daily-counts` was added to return average daily counts for probes, MAC addresses, and SSIDs from historical daily import tables (excluding today). PR #335
- New `stats-api` endpoint `GET /stats/ssids/export` was added to return filtered/sorted SSID statistics as a CSV download (without pagination limits), matching the SSID view filters. PR #358
- New SSID CSV export action was added to `monitor-dashboard` with authenticated download support, including loading state, disabled button, and success/error toast feedback. PR #358

### Changed

- `monitor-dashboard` now consumes the average-daily stats endpoint and renders three new `Average / day` cards for Probe Requests, SSIDs, and MAC addresses immediately after the `Total (unique)` cards. PR #335
- `monitor-dashboard` Live View toggle is now hidden on the SSID page and automatically resets to off when navigating between routes. PR #358

### Fixed

- Dashboard width/zoom responsiveness issues were fixed by relaxing page-width constraints across key dashboard views and header layout so content can use the full available viewport width more consistently. PR #358

## [3.0.0] - 2026-07-22

### Added

- New `stats` service for publishing daily and aggregate statistics from the home PostgreSQL source to Supabase, including models, migrations, and initial backfill tooling. PR #337
- New `stats-api` FastAPI service with Supabase-backed endpoints for totals, device stats, manufacturer data, Sankey data, and paginated SSID statistics. PR #337
- Firebase Bearer-token authentication middleware (`FIREBASE_CREDENTIALS_JSON`) and Redis response caching support were added to `stats-api`. PR #337
- New Supabase tables and pipelines for privacy-preserving MAC analytics (`mac_stats` with HMAC hashing) and daily unique snapshots (`unique_total_stats`). This will not be used as MAC table has been removed from Supabase due to memory limits. PR #337
- New monitor dashboard SSID page with server-side pagination/sorting/search and debounced query input. PR #337
- New FastAPI Cloud deploy workflow for `stats-api`. PR #337
- Logfire observability instrumentation was added to `stats-api` for runtime tracing and diagnostics. PR #345
- New combined deploy workflow (`.github/workflows/deploy.yml`) was added to orchestrate `stats-api` and `monitor-dashboard` deploys in one pipeline. PR #345

### Changed

- `monitor-dashboard` historical/statistical reads were migrated from Firebase Realtime Database to `stats-api`, while live probe updates remain on Firebase. PR #337
- Frontend API consumption was refactored to a shared authenticated GET client with Firebase ID-token injection and in-flight request de-duplication. PR #337
- Orchestrator DAG flow now calls the `stats` service after `aggregator`, with configurable base URL and timeout settings. PR #337
- Manufacturer and Sankey sections in the dashboard were optimized with lazy loading so expensive data loads only after card expansion. PR #337
- Deploy order was updated so `monitor-dashboard` deploy in `deploy.yml` waits for `stats-api` deploy completion.
- `deploy.yml` jobs are now path-aware: `stats-api` deploy runs only for `stats_api/**` changes and dashboard deploy runs only for `monitor_dashboard/**` changes (or manual dispatch). PR #345
- Live Probe Request card now shows explicit connection state in the interval badge (`Connecting...` while initializing, then `Live`) with gray/loading and red/connected pulse styling. PR #348

### Fixed

- Manufacturer world-map coloring now correctly uses ISO alpha-3 country codes from API responses instead of full country names. PR #337
- Device status rendering in the dashboard grid now refreshes when online-status data updates, preventing stale `Offline` states. PR #337
- Python test workflow discovery was scoped to the `tests/` directory to avoid importing runtime-only packages during CI collection. PR #337
- Live probe-count subscription startup no longer performs duplicate Firebase initialization reads; initial totals are aggregated once and emitted before incremental updates. PR #348
- Live probe-count listener bootstrap now ignores the initial `onChildAdded` seed event for existing device data, preventing startup overcount drift and removing UI count-offset dependence. PR #348

## [2.0.0] - 2026-07-12

### Added

- Sentry fatal-error logging integrated into the Go notifier services: `cloudflare-limit-notifier`, `collector-status-notifier`, and `firebase-limit-notifier`. PR #296
- Mattermost bot icon support added for Go services through service-name-based icon mapping, with custom bot icon assets under `resources/bot_icons/`. PR #296
- Datadog heartbeat status validation added to `collector-status-notifier` as the primary device-health source, with periodic checks and Datadog API integration for configured devices. PR #302
- New `FIREBASE_MONGO_BACKUP_ENABLED` usage flag added to `firebase-housekeeping` to control MongoDB backup behavior during cleanup workflows. PR #301
- `db-backup` workflow now includes `cleanup_local_files_task`, which deletes local temporary backup artifacts after successful upload. PR #307
- Internal Sentry fatal logging was added to `db-backup` via `internal/logging`, configurable through `SENTRY_DSN` and `SERVICE_NAME`. PR #307
- Aggregator now sends a Mattermost message when the workflow starts. PR #308
- New `home-server-limit-notifier` Go microservice added to monitor host SSD usage and send Mattermost reports on-demand via an HTTP trigger endpoint. PR #312
- New `orchestrator` added that now governs `aggregator`, `firebase-housekeeping` and `db_backup` services. Backup is now triggered after the main aggregation/housekeeping flow. PR #319
  - `aggregator` service restrucered to be an API with Celery worker that governs the import process.
- Added Datadog dashboard snapshot export for device monitoring, including home server visibility updates under `collector_metrics_agent/datadog/dashboard_snapshots/`. PR #333
- Redis-backed lookup cache helpers were added for SSID/MAC ID resolution in `aggregator` with a 1-hour TTL. PR #335

### Changed

- Changed Firebase cleanup to use batch-delete workflow. PR #267
- Firebase cleanup batch-delete flow now skips nodes for the current day to avoid removing fresh data. PR #267
- Go formatter automation updated to include a previously missing service target. PR #284
- README documentation updated and refined across multiple passes (wording, spelling, and clarity improvements).
- `collector-status-notifier` now performs device status checks every 5 minutes via Datadog and falls back to Firebase status checks when Datadog is unavailable. PR #302
- `firebase-housekeeping` logging was expanded with additional runtime messages for better operational visibility.
- Aggregator `/aggregate` endpoint now behaves idempotently for concurrent triggers by returning the already running workflow id instead of creating a duplicate active workflow. PR #319
- `collector` capture scheduling now supports a `CAPTURE_24_7` configuration flag to allow continuous capture outside working-hours windows. PR #319
- Dashboard live-toggle condition was updated to support always-live operation. PR #327
- `collector-metrics-agent` dependency manifests were updated and the settings template filename typo was fixed (`settings.py.template.py` -> `settings.py.template`). PR #333
- Aggregator stats publishing now accepts an optional import date and uses it when publishing daily stats, so day-after imports publish daily aggregates for the imported day instead of only for today. PR #335
- Aggregator import lookup flow now resolves SSID and MAC IDs through dedicated helpers instead of preloading full SSID/MAC tables into memory before import.
- Aggregator now stores initial workflow `STARTED` status in Redis with a 5-hour TTL to reduce stale in-progress status keys after unexpected worker shutdowns.
- Invalid-channel skip logging during import was lowered from warning to info to reduce noisy alerting.

### Fixed

- `db-backup` Conductor Docker healthcheck endpoint was corrected from `/api/health` to `/health`, resolving false `unhealthy` container status after worker runs.
- `orchestrator` db backup trigger now accepts both JSON and plain-text Conductor workflow id responses (including `raw_response` fallback), preventing false "missing workflow id" failures. PR #319
- `db-backup` upload pipeline and worker now emit detailed runtime diagnostics (input validation, file size/path, object key, elapsed time, and upload errors) to improve R2 upload troubleshooting. PR #324
- `db-backup` upload timeout handling was improved for backup artifact transfers to R2. PR #324
- `monitor-dashboard` live Probe Request card no longer spikes to an incorrect percentage on first live update due to stale-state percentage calculation. PR #327
- `collector` and `aggregator` now validate channel values before persistence, preventing invalid channel IDs (e.g., `124`) from causing `captured_info_channel_fkey` foreign key failures during import. PR #329
- `aggregator` service restart policy was updated to `unless-stopped` in Docker Compose. PR #331

## [1.0.0] - 2026-05-30

### Added

- Public stable release of the PNLS-DC distributed data collection platform.
- Distributed edge `collector` service for Wi-Fi probe request capture with preprocessing and encryption before ingestion.
- Event-driven ingestion layer on Firebase Realtime Database for real-time capture workflows.
- Daily batch ETL (`aggregator`) into PostgreSQL with decryption, transformation, loading, and daily statistics publishing.
- Operational maintenance services:
  - `firebase-housekeeping` for periodic Firebase cleanup and MongoDB archival.
  - `collector-status-notifier` for device availability checks and alerting.
  - `firebase-limit-notifier` and `cloudflare-limit-notifier` for usage tracking and quota safety.
  - `collector-metrics-agent` for edge device metrics collection and Datadog reporting.
- PostgreSQL analytics storage and migration workflow for structured research data.
- `db-backup` workflow for automated PostgreSQL backup, encryption, compression, and Cloudflare R2 upload.
- `monitor-dashboard` frontend for authenticated monitoring, real-time updates, and analytics visualization.
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

