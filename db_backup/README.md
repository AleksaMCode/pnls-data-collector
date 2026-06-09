# db_backup

Conductor-orchestrated PostgreSQL backup worker implemented in Go.

Pipeline per task execution:
1. `pg_dump` database export
2. AES-256-GCM encryption
3. gzip compression
4. upload to S3-compatible storage (Cloudflare R2)
5. local artifact cleanup

Returned task output includes uploaded object path and key.

## Setup

1. Copy `.env` template and fill in values:
   ```bash
   cp .env.template .env
   ```

2. Fill required variables in `.env`

| Variable | Description                                                                                               |
|----------|-----------------------------------------------------------------------------------------------------------|
| **Database** | Either set `DB_DSN` (full connection string) or `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` |
| `DB_BACKUP_ENCRYPTION_KEY` | AES-256 key: 32 bytes, base64- or hex-encoded (The password can be created using the `genaeskey.sh`.)     |
| `R2_ACCESS_KEY` | Cloudflare R2 access key                                                                                  |
| `R2_SECRET_KEY` | Cloudflare R2 secret key                                                                                  |
| `R2_BUCKET_NAME` | Bucket name for backup artifacts                                                                          |
| `R2_BUCKET_PUBLIC_URL` | Base URL for public object access (e.g. `https://pub-xxx.r2.dev`)                                         |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID (for R2 endpoint; omit if using `R2_ENDPOINT`)                                      |
| `SENTRY_DSN` | Optional Sentry DSN for fatal error reporting                                                               |
| `SERVICE_NAME` | Service name shown in Sentry (defaults to `db_backup_worker`)                                               |

## Run with Docker

```bash
docker compose -f db_backup/docker-compose.yml up --build
```

> [!NOTE]
> 
> The API listens on port `8080`.

At startup the worker registers:
- task definition from `workflows/task_definition.json`
- workflow definition from `workflows/workflow_definition.json`
- scheduler definition from `workflows/schedule_definition.json`

The workflow runs four Conductor simple tasks in sequence:
- `pg_dump_task`
- `encryption_task`
- `compress_task`
- `upload_to_r2_task`
- `cleanup_local_files_task`

## Local run (without Docker)

```bash
cd db_backup
go run ./cmd/worker
```

## Daily cron trigger

Schedule is configured for daily execution at 23:00 (`0 0 23 * * ?`).

```bash
0 23 * * * curl -sS -X POST "http://localhost:8080/api/workflow/db_backup_workflow?version=1" -H "Content-Type: application/json" -d "{}" >> /var/log/db_backup_trigger.log 2>&1
```