# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `firebase-housekeeping` deletes now also delete the Firebase `stats` node, which nothing reads anymore. It's still left out of the MongoDB backup.

### Deprecated

- `aggregator` `publish_daily_stats_data` and `publish_daily_stats_capture_data`, which publish to the Firebase `stats` node, are now deprecated like the other Firebase stats publishers. Only the `aggregator` tools still call them.

### Removed

- `monitor-dashboard` no longer has the Firebase readers of the `stats` node (`fetchTotalStats`, `fetchSankeyData` and the other 10), which the `stats-api` client replaced. Only the live data (device heartbeats, live rows and the live probe request count) is still read from Firebase.

## [3.3.0] - 2026-11-27

### Added

- New `ssid-geo-mapper` service implementation. PR #372
- Mattermost notifications for `ssid-geo-mapper`. PR #372
- New SSID GEO database views. PR #372
- `monitor-dashboard` Manufacturer data accordion on the home page now shows a hover tooltip prompting the user to expand it while collapsed, matching the Sankey accordion. PR #417
- Supabase `ssid_stats` table now has `geo` (JSONB list of reduced geolocations), `geo_updated` and a generated `has_geo` column, with indexes on `(has_geo, last_seen)` and `geo_updated` (migration `20261123120000_add_geo_to_ssid_stats`).
- `stats` service now publishes reduced SSID geolocations to Supabase in a separate step of `POST /stats`. It publishes the geolocations created on or after the newest `geo_updated` date in Supabase and only fills rows that have no geolocation yet. Coordinates are rounded to 2 decimals (about 1 km). PR #421
- New `stats` tool `initial_ssid_geo_publisher` that publishes all SSID geolocations to Supabase, replacing already published values. PR #421
- `stats-api` endpoint `GET /stats/ssids` now returns `has_geo` and `geo` for each SSID and supports `sort_by=has_geo`. `GET /stats/ssids/export` accepts the same sort while its CSV columns are unchanged. PR #421
- `monitor-dashboard` SSIDs view now has a sortable Geolocation column and a world map below the table that shows the locations of the selected SSID. PR #421
- New `Security` GitHub workflow that runs `npm audit` for `monitor-dashboard`, `govulncheck` for every Go module and a Trivy scan of the React and Go Docker images. It runs on dependency, Go source and `Dockerfile` changes and on a weekly schedule. PR #423
- Uptime Kuma was added to the root `docker-compose.yml` for uptime monitoring of the services running on the home server and of the cloud-hosted service (e.g. `stats-api`). PR #423
- `collector-status-notifier` can now send a push heartbeat to Uptime Kuma after every status check, enabled with `KUMA_PUSH_ENABLED` and pointed at the monitor with `KUMA_PUSH_URL`. PR #423
- `Security` GitHub workflow now also runs `pip-audit` for every Python `requirements.txt` file, and the Python services, `util` and `tests` have `audit` and `audit-fix` Makefile targets for it. PR #426
- `Security` GitHub workflow now also scans the Python Docker images (`aggregator`, `firebase-housekeeping`, `ssid-geo-mapper`, `stats` and `stats-api`) with Trivy. PR #426
- `stats-api` `audit` and `audit-fix` Makefile targets now also cover `pyproject.toml`, which the FastAPI Cloud deployment uses. A new `scripts/check_dependencies_sync.py` check fails when `pyproject.toml` and `requirements.txt` list different dependencies, and it runs in the `Security` GitHub workflow. PR #426
- New `scripts/check_util_requirements_sync.py` check that fails when a Python service pins a shared dependency differently than `util/requirements.txt`. It runs in the `Security` GitHub workflow. PR #426
- Root `requirements-dev.txt` with the Python development tools (`black`, `isort`, `pip-audit`, `pre-commit` and `ruff`) that the GitHub workflows and the root `Makefile` use. PR #426
- Root `Makefile` with `fmt`, `lint`, `audit-python`, `audit-fix-python`, `scan-secrets` and `check-util-requirements-sync` targets. `fmt` and `lint` also have a target per language (`-python`, `-go`, `-react` and `-markdown`), and `lint` has one for the Dockerfiles (`-docker`). PR #426
- ESLint for `monitor-dashboard`, with a `lint` Makefile target and a step in the code style workflow. The findings that existed for the `react-hooks/set-state-in-effect` rule are recorded in `eslint-suppressions.json`, so only new ones fail. PR #426
- `golangci-lint` linters for all Go modules (the standard set plus `revive`, `gocritic`, `modernize`, `errorlint` and others), with a `lint` Makefile target in every module. PR #426
- Ruff linter for the Python code (`ruff.toml`), with a step in the Python code style workflow. PR #426
- New `Secret Scan` GitHub workflow that runs Gitleaks over the full git history on every pull request, every push to `master`, on a weekly schedule and on demand. Accepted findings are listed in `.gitleaksignore`, and a Gitleaks pre-commit hook scans staged changes. PR #426
- Prettier and markdownlint for the Markdown files, installed from a root `package.json`, with a new `Markdown Code Style Check` GitHub workflow. The `npm audit` job of the `Security` GitHub workflow also audits the root `package-lock.json`. PR #426
- Hadolint for the Dockerfiles, with a new `Docker Code Style Check` GitHub workflow and a pre-commit hook that both run the pinned `hadolint/hadolint` Docker image. Ignored rules are listed in `.hadolint.yaml`. PR #426
- `util-go` has a new `objectstore` package for uploads to S3-compatible storage such as Cloudflare R2, which `db-backup` and `firebase-limit-notifier` now use. PR #428
- Root `Makefile` `test` target, which runs the Python and Go tests, with `test-python`, `test-python-unit`, `test-python-integration`, `test-go`, `test-go-unit` and `test-go-integration` targets. The Go modules with integration tests have a `test-integration` Makefile target. PR #428
- Root `.python-version` file, which the Python GitHub workflows read their Python version from. PR #428

### Changed

- SSID GEO tables were migrated to include a `create_date` column. PR #372
- `monitor-dashboard` API-backed dashboard reads were migrated to TanStack Query with shared query-client defaults, replacing ad-hoc component fetch effects with query-keyed caching and reuse. PR #409
- `monitor-dashboard` device lists are now sourced dynamically from `/stats/devices` across dashboard navigation, live probe subscriptions, and device-route validation instead of hardcoded `RPI-*` arrays. PR #409
- `stats-api` data series responses (all devices and per device) now include a `dates` array of ISO dates aligned index-for-index with the series; `dayCounts` is kept for backward compatibility. PR #415
- `collector` status heartbeat timestamp and Firebase status node date are now derived from the configured `TIMEZONE` instead of the host's local time. PR #415
- `collector-status-notifier` now derives the status node date and parses heartbeat timestamps in the configured `TIMEZONE` instead of the container's timezone. PR #415
- Go code style workflow now pins `golangci-lint` to `v2.12.2`, the last release that supports Go 1.25. PR #415
- `firebase-limit-notifier` and `db-backup` integration tests now use the `pgsty/silo` image, a MinIO-compatible fork, in place of the removed `minio/minio` image. PR #415
- `monitor-dashboard` SSIDs table now shows first seen and last seen dates as `DD/MM/YYYY` with a 12-hour AM/PM time (e.g. `05/03/2026, 03:07:09 PM`) in English instead of the US month-first format. PR #416
- `monitor-dashboard` side menu rows are now 40px tall with 20px icons and more spacing between icon and label; the sizing is scoped to the side menu, and long device names still wrap in the Devices sub-list. PR #419
- `monitor-dashboard` side menu footer now truncates a long username or email with an ellipsis instead of pushing the options button out of view. PR #419
- `ssid-geo-mapper` now aborts the whole run on the first WiGLE `429`, `401` or `403` instead of retrying each SSID up to 10 times with exponential backoff or carrying on with the next SSID; `410` is no longer retried either. PR #420
- `ssid-geo-mapper` now fetches 240 SSIDs per run (`WIGLE_BATCH_SIZE`) and caps the run at 250 WiGLE requests, leaving headroom below the daily quota. PR #420
- `ssid-geo-mapper` now logs the WiGLE response body on every non-2xx status, and its Mattermost summary reports requests sent, SSIDs with locations, SSIDs without results, failures by reason and, on abort, the status and request index that stopped the run. PR #420
- `ssid` table now tracks failed WiGLE lookups in the new `failed_attempts`, `last_failure_reason` and `last_attempt_at` columns (migration `000010`). PR #420
- `ssid-geo-mapper` now maps SSIDs that never failed first; previously failed SSIDs only fill the rest with the batch, fewest failures and least recently tried first. The Mattermost summary reports how many of them were retried. PR #420
- `ssid-geo-mapper` no longer marks an SSID as mapped without GEO data when WiGLE answers `200` with an unusable payload; the SSID stays unmapped and is retried on the next run. PR #420
- `firebase-limit-notifier` is now a long-running HTTP microservice with a `POST /check` trigger endpoint (`HTTP_PORT`, `CHECK_ENDPOINT_PATH`) and a Docker setup, instead of a one-shot program. The home server cron job now calls the endpoint on the same weekly schedule. PR #423
- Go was upgraded from 1.25.5 to 1.27.4 in all Go services, their Docker images and the GitHub workflows, and the Go dependencies were upgraded. PR #423
- Node was upgraded to 26.13 for `monitor-dashboard`, in its Docker image and the GitHub workflows. PR #423
- `monitor-dashboard` now overrides `@grpc/grpc-js`, a transitive dependency of `firebase`, to a patched `1.14.x` release, and its Docker image updates the bundled npm to `11.21.3`, to clear known vulnerabilities. PR #423
- All GitHub workflows now run on `ubuntu-26.04` instead of `ubuntu-latest`. PR #423
- Go tests and Go code style workflows now also run when `.go-version`, `go.mod` or `go.sum` change. PR #423
- Go code style workflow now pins `golangci-lint` to `v2.15.0` to match Go 1.27.4. PR #423
- Python Docker images now install the Debian security updates at build time, remove `pip` from their final filesystem, and install the service and `util` requirements in one `pip` command so that conflicting pins fail the build. PR #426
- Python dependencies were upgraded to clear known vulnerabilities: `python-dotenv` to `1.2.2`, `pymongo` to `4.18.3`, `requests` to `2.33.0`, and `geopy` to `2.5.0`. PR #426
- `orchestrator` was upgraded from Airflow `3.1.3` to `3.4.0`, in the Docker images of its `docker-compose.yml` and in its requirements. The Compose services no longer mount `requirements.txt`, which was never installed in the containers. PR #426
- Python Docker images now install the requirements and remove `pip` in one `RUN` instruction, and the `collector-status-notifier` and `firebase-limit-notifier` images download the Go modules and build in one `RUN` instruction. PR #426
- `stats-api` now uses `logfire` `5.2.0` and pins `opentelemetry-api` to `1.45.2`. PR #426
- `black` was upgraded to `26.10.1` and `isort` to `9.0.2`, in pre-commit and in the Python code style workflow. PR #426
- Prettier was upgraded to `3.10.1` for `monitor-dashboard`. PR #426
- Go code style workflow now runs one `golangci-lint run` step for all modules, which checks both formatting and linting. PR #426
- `formatter-go.sh` and `formatter-python.sh` were replaced by the `fmt` targets of the root `Makefile`, and the deprecated `start_aggregator.sh` was removed. PR #426
- `db-backup` now uses the `util-go` `logging` and `objectstore` packages instead of its own `internal/logging` and `internal/storage` packages, and its Docker image builds from the repository root so it can include `util-go`. PR #428
- `firebase-limit-notifier` now uploads its charts with the `util-go` `objectstore` package. PR #428
- Go Docker images (`cloudflare-limit-notifier`, `collector-status-notifier`, `db-backup` and `firebase-limit-notifier`) now upgrade the Alpine packages at build time, so they get security fixes before a new `alpine:3.22` image is released, such as OpenSSL `3.5.9-r2` for CVE-2026-124709. PR #428
- `aggregator` Postgres is pinned to `postgres:16` instead of `postgres:latest`, as Postgres can't start on data created by an older major version. `firebase-housekeeping` MongoDB is pinned to `mongo:8.2.3` instead of `mongo:latest`. PR #428
- `aggregator` pins `packaging` to `25.0`, which Celery's Redis transport imports but not every `kombu` release declares. PR #428
- All GitHub workflows now use `actions/checkout` v7, and the Python workflows `actions/setup-python` v7. PR #428

### Fixed

- `monitor-dashboard` Captured Info chart now uses month-year labels (e.g. `oct-25`) to prevent month-label collisions across years. PR #402
- `stats-api` Logfire initialization order was fixed by moving observability setup to explicit startup initialization. PR #404
- `monitor-dashboard` full-history totals charts (probe requests, SSIDs, MAC addresses) on the main and device views now label the x-axis with the real series dates including the year, fixing overlapping points once the history exceeded one year. PR #415
- `monitor-dashboard` device table no longer shows devices as offline and not capturing for up to 10 minutes after midnight; the status check now falls back to the previous day's Firebase node until the first heartbeat of the new day. PR #415
- `monitor-dashboard` device online check now compares the heartbeat and the current time as Europe/Paris wall time, so the result no longer depends on the viewer's timezone. PR #415
- `collector-status-notifier` no longer reports devices as having no status right after midnight; it falls back to the previous day's Firebase status node. PR #415
- `monitor-dashboard` SSIDs table no longer leaves an empty gap between the last row and the pagination controls on tall screens; the table now ends after its last row and only scrolls when it exceeds the viewport height. PR #416
- `monitor-dashboard` home page Manufacturer data and Sankey accordions no longer lose their bottom border; every accordion now keeps its full border and border radius. PR #417
- `monitor-dashboard` Manufacturer data and Sankey accordion summaries now keep their titles as accessible names; the expand tooltip text is exposed as a description instead of replacing the label for screen readers. PR #417
- `monitor-dashboard` pages with data grids (home and SSIDs) no longer overflow horizontally when zooming in or reopening the side menu; the main content area can now shrink with the viewport. PR #419
- `monitor-dashboard` side menu toggle is smoother: the page content now resizes once after the panel animation ends instead of redrawing every chart and data grid mid-animation, and menu labels fade instead of being mounted and unmounted. PR #419
- `monitor-dashboard` collapsed side menu items keep their labels as accessible names for screen readers, and menu icons no longer shift position when toggling. PR #419
- `firebase-limit-notifier`, `cloudflare-limit-notifier` and `home-server-limit-notifier` no longer terminate when the Mattermost report can't be sent; the check request now fails with `502` and the service stays available. PR #423
- `db-backup` compress step now fails when the archive file can't be closed, instead of reporting a possibly incomplete archive as successful. PR #426
- `monitor-dashboard` stat cards now update their trend when only the `trend` value changes. PR #426
- `aggregator` Firebase helper that deletes the sankey data is now named `delete_sankey`; it was defined as a second `delete_manufacturers` and replaced the first one. PR #426
- `aggregator` migration `000001` now adds the unique constraint on `location_mapping.device` that the `ON CONFLICT (device)` upsert in migration `000002` and the `LocationMapping` model rely on; it was missing from the original dump, so a database built from the migrations could not be seeded. PR #428
- `firebase-limit-notifier` no longer exits when it can't set up the R2 client; the usage report is still sent to Mattermost, without the chart. PR #428

## [3.2.0] - 2026-08-09

### Added

- Redis-backed offline state caching was added to `collector-status-notifier` to persist per-device outage state (`first_discovered_at`, `updated_at`) until recovery. PR #356
- Docker support was added for `collector-status-notifier`. PR #356
- `cloudflare-limit-notifier` now exposes an HTTP trigger endpoint (`POST /check`) for on-demand Cloudflare R2 usage checks and Mattermost reporting. PR #367
- Docker support was added for `cloudflare-limit-notifier`. PR #367

### Changed

- `collector-status-notifier` now sends Mattermost alerts only on device status transitions (first offline and first online recovery) instead of repeated offline checks. PR #356
- Go service logging now writes to both rotating file logs and stdout/stderr (console), so container runtime logs are visible while preserving local log rotation. PR #385
- `cloudflare-limit-notifier` Cloudflare GraphQL client now uses `retry-go` with retry behavior for `429` and `5xx` responses, respects `Retry-After` when present, and logs retry attempts. PR #367
  - Cloudflare GraphQL retry configuration in `cloudflare-limit-notifier` is now environment-driven via `CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS`, `CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS`, and `CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS`. PR #367
- Home server cron trigger for Cloudflare usage checks now sends a direct HTTP `POST` request to the notifier endpoint instead of invoking a shell wrapper script. PR #367

### Fixed

- `monitor-dashboard` side-menu `Home` item spacing was aligned with `SSIDs` and `Devices` by removing custom text-offset styling, fixing inconsistent icon-to-label distance. PR #377

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
