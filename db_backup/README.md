# db_backup

Conductor-orchestrated PostgreSQL backup worker implemented in Go.

Pipeline per task execution:
1. `pg_dump` database export
2. AES-256-GCM encryption
3. gzip compression
4. upload to S3-compatible storage (Cloudflare R2)

Returned task output includes uploaded object path and key.

## Setup

1. Copy env file:

```bash
cp .env.template .env
```

2. Fill `.env` with database, R2, and `DB_BACKUP_ENCRYPTION_KEY`.

## Run with Docker

```bash
docker compose -f db_backup/docker-compose.yml up --build
```

At startup the worker registers:
- task definition from `workflows/task_definition.json`
- workflow definition from `workflows/workflow_definition.json`
- scheduler definition from `workflows/schedule_definition.json`

The workflow runs four Conductor SIMPLE tasks in sequence:
- `pg_dump_task`
- `encryption_task`
- `compress_task`
- `upload_to_r2_task`

Schedule is configured for daily execution at 23:00 (`0 0 23 * * ?`) using the stack timezone (`Europe/Paris`).

## Local run (without Docker)

```bash
cd db_backup
go run ./cmd/worker
```
