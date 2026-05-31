# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Changed Firebase cleanup to use batch-delete workflow. #267
- Firebase cleanup batch-delete flow now skips nodes for the current day to avoid removing fresh data. #267
- Go formatter automation updated to include a previously missing service target. #284
- README documentation updated and refined across multiple passes (wording, spelling, and clarity improvements).

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
