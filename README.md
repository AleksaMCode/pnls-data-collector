# Preferred Network List Sniffer Data Collector - PNLS-DC

![Deploy](https://github.com/AleksaMCode/pnls-data-collector/actions/workflows/deploy.yml/badge.svg?branch=master)
[![License: GPL-2.0](https://img.shields.io/badge/license-GPLv2.0-red.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
[![Python 3.13.7](https://img.shields.io/badge/python-3.13.7-blue.svg)](https://www.python.org/downloads/release/python-3137/)
[![Code style (Python): black](https://img.shields.io/badge/code%20style%20(python)-black-000000.svg)](https://github.com/psf/black)
[![Go 1.25.5](https://img.shields.io/badge/go-1.25.5-00ADD8.svg)](https://go.dev/dl/)
[![Code style (Go): golangci-lint](https://img.shields.io/badge/code%20style%20(go)-golangci--lint-00ADD8.svg)](https://golangci-lint.run/)
[![Node 22.19.0](https://img.shields.io/badge/node-22.19.0-3C873A.svg)](https://nodejs.org/en/blog/release/v22.19.0)
[![Code style (JS/TS): Prettier](https://img.shields.io/badge/code%20style%20(JS/TS)-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
![Python tests](https://github.com/AleksaMCode/pnls-data-collector/actions/workflows/python-tests.yml/badge.svg?branch=master)
![Go tests](https://github.com/AleksaMCode/pnls-data-collector/actions/workflows/go-tests.yml/badge.svg?branch=master)
![](https://img.shields.io/github/v/release/AleksaMCode/pnls-data-collector)


A distributed, microservice system for capturing Wi‑Fi [probe requests](https://en.wikipedia.org/wiki/IEEE_802.11#Management_frames) ([SSIDs](https://en.wikipedia.org/wiki/Service_set_(802.11_network)), [MACs](https://en.wikipedia.org/wiki/MAC_address), ...), with hybrid [event-driven](https://en.wikipedia.org/wiki/Event-driven_architecture) ingestion, batch [ETL](https://en.wikipedia.org/wiki/Extract,_transform,_load), real-time analytics, and centralized observability. Built for ongoing research into privacy protection in Wi-Fi networks.

<p align="center">
<img
src="./resources/pnls-dc-architecture.svg?raw=true"
alt="PNLS-DC system overview"
width="100%"
class="center"
/>
<p align="center">
    <label><b>Fig. 1</b>: PNLS-DC <code>3.0.0</code> system overview</label>
    </p>
</p>

> [!WARNING]
> While probe requests are essential for network discovery and connectivity establishment, they may also be exploited for malicious purposes, including the tracking and profiling of user behavior. These privacy risks have prompted the development of mitigation strategies, such as MAC address randomization, and have served as a primary motivation for the research undertaken in this project.

> [!NOTE]
> - The majority of this research is carried out as part of a collaboration with the Computer Security Team at [CERN](https://home.cern/). All collector devices are currently deployed at CERN’s Meyrin site, where data collection activities are taking place.
> - The [project's board](https://github.com/users/AleksaMCode/projects/3) can be used to track current research and project progress.
> - The initial scope of work [presentation](https://drive.google.com/file/d/1pYm6buyRmGwN5MY7c8_tj93C0iddurI3/view) can be found here.


## Architecture Overview

1. **Distributed edge devices (`collector`)**
   - Captures Wi-Fi probe requests.
   - Preprocesses and [RSA-encrypts](https://en.wikipedia.org/wiki/RSA_cryptosystem) data.
   - Pushes data to [Firebase Realtime Database](https://firebase.google.com/docs/database).
     - It also keeps a local copy of the data.

> [!NOTE] 
> The `collector` service started as a separate project [PNLS](https://github.com/AleksaMCode/Preferred-Network-List-Sniffer); it was used as a starting point when writing this service.

<p align="center">
<img
src="./resources/collector-devices.jpg?raw=true"
alt="PNLS-DC system overview"
width="90%"
class="center"
/>
<p align="center">
    <label><b>Fig. 2</b>: <code>collector</code> devices (RPi 4 with a colling case) with an <a href="https://alfa-network.eu/awus036acs">AWUS036ACS</a> antenas</label>
    </p>
</p>

2. **Firebase Realtime Database**
   - Event-driven ingestion from edge devices.
   - Temporary storage and staging for batch ETL.
   - Real-time updates to the React UI and daily statistics.

3. **Scheduled/continuous microservices**
   - Daily batch ETL to PostgreSQL.
     - `aggregator` runs every day just after $12$ AM, starting the process of extracting data from Firebase, decrypting, transforming, and finally loading it into PostgreSQL. It also sends a [Mattermost](https://github.com/mattermost/mattermost) summary.

<p align="center">
<img
src="./resources/aggregator-mattermost.png?raw=true"
alt="Aggregator Mattermost message"
width="50%"
class="center"
/>
<p align="center">
    <label><b>Fig. 3</b>: Example <code>aggregator</code> Mattermost message</label>
    </p>
</p>

   - `stats` writes daily statistics to [Supabase](https://github.com/supabase/supabase) Postgres DB. This data is then read by the `monitor-dashboard` using the `stats-api`.

<p align="center">
<img
src="./resources/stats-api-swagger.png?raw=true"
alt="`stats-api` Swaggger Docs"
width="90%"
class="center"
/>
<p align="center">
    <label><b>Fig. 4</b>: Example <code>stats-api</code> (<code>3.0.0</code>) Swagger Docs</label>
    </p>
</p>

   - Firebase cleanup every $5$ days (`firebase_housekeeping`).
     - Starting at after `aggreagator`, it migrates data to MongoDB as backup, and deletes old Firebase nodes in order to stay within the [free 1 GB limit](https://firebase.google.com/pricing).
   - Device online status monitoring.
     - `collector_status_notifier` checks device status every $5$ minutes during the capture window[^1] and sends Mattermost alerts if a device is offline.
   - Continuous edge device monitoring.
     - `collector_metrics_agent` collects and sends edge device metrics data to the [Datadog](https://en.wikipedia.org/wiki/Datadog) storage where it is displayed in a monitoring dashboard.
     - Same agent code is also deployed on the home server.
   - Weekly Firebase usage reporting (`firebase_limit_notifier`).
     - Computes Firebase usage, generates a pie chart (uploaded to [Cloudflare R2](https://www.cloudflare.com/products/r2/)), and sends a Mattermost report.

<p align="center">
<img
src="./resources/firebase-limit-notifier-mattermost.png?raw=true"
alt="Firebase limit notifier Mattermost message"
width="50%"
class="center"
/>
<p align="center">
    <label><b>Fig. 5</b>: Example <code>firebase_limit_notifier</code> Mattermost message</label>
    </p>
</p>

   - Weekly Cloudflare usage reporting (`cloudflare_limit_notifier`).
     - It computes the current R2 usage (storage usage and class A and B operations) in order to stay within the [free limits](https://developers.cloudflare.com/r2/pricing/#free-tier).

<p align="center">
<img
src="./resources/cloudflare-limit-notifier-mattermost.png?raw=true"
alt="Cloudflare limit notifier Mattermost message"
width="50%"
class="center"
/>
<p align="center">
    <label><b>Fig. 6</b>: Example <code>cloudflare_limit_notifier</code> Mattermost message</label>
    </p>
</p>

4. **Warehousing and analytics**
   - PostgreSQL for structured analytics data.
     - Stores structured, queryable data (SSIDs, MACs, locations, timestamps, etc.)
     - Source for analytics and historical reporting.
     - Schema definition (`aggregator/migrations`) and migration done using [migrate](https://github.com/golang-migrate/migrate).
   - MongoDB used by archive flow.

5. **Database Backup Service (`db_backup`)**
   - Provides a PostgreSQL backup workflow orchestrated by [Netflix Conductor](https://en.wikipedia.org/wiki/Conductor_(software)).
   - This workflow is triggered every day as the last part of the aggregation workflow triggered by the Apache Airflow `orchestrator`.
   - Pipeline tasks:
     1. `pg_dump_task` - dump PostgreSQL to `backup.sql`
     2. `encryption_task` - [AES-256-GCM](https://en.wikipedia.org/wiki/Galois/Counter_Mode) encrypt to `backup.sql.enc`
     3. `compress_task` - gzip to `backup.sql.enc.gz`
     4. `upload_to_r2_task` - upload artifact to Cloudflare R2/S3-compatible storage
     5. `cleanup` - removed local copy of the encrypted DB.

6. **Frontend (`monitor_dashboard`)**
   - React UI with [Firebase Authentication](https://firebase.google.com/docs/auth).
   - Reads daily statistics written by `stats` service for the analytics dashboard.
   - Real-time and daily aggregated analytics views.
   - Deployed to [Firebase Hosting](https://firebase.google.com/docs/hosting).

<p align="center">
<img
src="./resources/pnls-dc-ui.png?raw=true"
alt="Part of the monitoring dashboard"
width="90%"
class="center"
/>
<p align="center">
    <label><b>Fig. 6</b>: Part of the monitoring dashboard <code>1.0.0</code></label>
    </p>
</p>

7. **Observability**
   - [Sentry](https://docs.sentry.io/product/explore/logs/) for centralized error tracking.
     - Using both Mattermost notifications (compatible with Slack-style webhooks from Sentry) and email notifications.
   - Datadog for edge devices (`collector`) metrics dashboard tracking.
   - Pydantic's [Logfires](https://github.com/pydantic/logfire), an observability platform built on OpenTelemetry, is used for tracking of `stats-api`.

## Key Characteristics

- Microservice-based, independently deployable components (ETL, monitoring, usage check, cleanup, etc.).
- Hybrid architecture: event-driven ingest + scheduled (batch) jobs.
  - Edge devices push events in real time; scheduled services handle batch ETL, cleanup, and reporting.
  - Two-stage transformation: edge preprocessing + server-side ETL.
- Data lifecycle management: old Firebase data is migrated or removed every $5$ days to stay within quota.
- Security/privacy: edge encryption and server-side controlled processing.
- Operational monitoring through status checks and usage reports.
- Centralized alerting through Sentry and webhook channels.
- Real-time data view: UI shows live device status, SSIDs, probe request count, and processed analytics.

## Deployment

- Dashboard is deployed via Firebase Hosting and `stats-api` is deployed via [FastAPI Cloud](https://fastapicloud.com/) using deploy GitHub workflow.
- Python and Go services can run as standalone processes or containers.
- `db_backup/docker-compose.yml` runs Conductor + backup worker stack.
- `orchestrator` runs the aggregation workflow with Firebase cleanup, stats service and it triggers `db-backup`.
 
[^1]: Current capture window is 24/7.