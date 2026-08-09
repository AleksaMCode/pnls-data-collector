# Cloudflare Limit Notifier (`cloudflare_limit_notifier`)

`cloudflare_limit_notifier` is a microservice that exposes an HTTP endpoint for on-demand Cloudflare R2 usage checks.

Current implementation includes:

- `r2OperationsAdaptiveGroups` for operation counts (Class A / Class B).
- `r2StorageAdaptiveGroups` for storage usage (`payloadSize + metadataSize`), using the latest point per bucket.
- Monthly window from first day of current month until now.
- HTTP trigger endpoint for running the check and sending a Mattermost report.

## Free-tier limits

- Storage: `10 GB / month`
- Class A operations: `1,000,000 / month`
- Class B operations: `10,000,000 / month`

## Setup

1. Copy/fill `.env` (already scaffolded) with:
   - `HTTP_PORT` (required)
   - `CHECK_ENDPOINT_PATH` (required, e.g. `/check`)
   - `CLOUDFLARE_API_TOKEN` (required)
   - `CLOUDFLARE_ACCOUNT_ID` (required)
2. Optional:
   - `CLOUDFLARE_R2_BUCKET_FILTER` to report only one bucket.
   - `CLOUDFLARE_GRAPHQL_ENDPOINT` (defaults to `https://api.cloudflare.com/client/v4/graphql`).
   - `CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS` (defaults to `5`).
   - `CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS` (defaults to `1`).
   - `CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS` (defaults to `30`).

## Run

```bash
go run .
```

## Trigger check

```bash
curl -X POST http://localhost:<HTTP_PORT><CHECK_ENDPOINT_PATH>
```

## Docker

```bash
docker compose up --build
```
