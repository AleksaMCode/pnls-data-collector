# Firebase Housekeeping

FastAPI microservice that migrates Firebase data to MongoDB and cleans up Firebase nodes (bi-monthly cleanup).

## Setup

1. Copy `.env` template and fill in values:
   ```bash
   cp .env.template .env
   ```
2. Place `firebase_credentials.json` in this directory (or use the template).

## Run with Docker

From the **project root**:

```bash
docker compose -f firebase_housekeeping/docker-compose.yml up -d
```

Or from this directory:

```bash
docker compose up -d
```

> [!NOTE]
> 
> The API listens on port `9090` (or `SERVER_PORT` from `.env`).

## Bi-monthly cron trigger

Trigger the delete workflow on the 1st and 15th of each month at 5:00 AM:

```bash
0 5 1,15 * * curl -sS -X DELETE "http://localhost:9090/delete" >> /var/log/firebase_housekeeping.log 2>&1
```