# Home Server Limit Notifier (`home_server_limit_notifier`)

`home_server_limit_notifier` is a Go microservice that exposes an HTTP endpoint for on-demand SSD usage checks.

When triggered, it:

- reads filesystem usage for a configured mount path (default `/`)
- computes used/free/total storage and usage percentage
- sends a plain-text report to Mattermost
- returns `200 OK` to the caller on success

## Setup

1. Copy `.env.template` to `.env`.
2. Fill required values:
   - `MATTERMOST_WEBHOOK_URL` (required)
3. Optional values:
   - `HTTP_PORT` (default: `8080`)
   - `CHECK_ENDPOINT_PATH` (default: `/check`)
   - `DISK_MOUNT_PATH` (default: `/`)
   - `SENTRY_DSN`

## Run

```bash
go run .
```

## Trigger check

```bash
curl -X POST http://localhost:8080/check
```
