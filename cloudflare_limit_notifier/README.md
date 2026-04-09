# Cloudflare Limit Notifier (`cloudflare_limit_notifier`)

`cloudflare_limit_notifier` is a microservice that fetches Cloudflare R2 monthly usage using the Cloudflare GraphQL API and compares usage against free-tier limits.

Current implementation includes:

- `r2OperationsAdaptiveGroups` for operation counts (Class A / Class B).
- `r2StorageAdaptiveGroups` for storage usage (`payloadSize + metadataSize`), using the latest point per bucket.
- Monthly window from first day of current month until now.

## Free-tier limits

- Storage: `10 GB / month`
- Class A operations: `1,000,000 / month`
- Class B operations: `10,000,000 / month`

## Setup

1. Copy/fill `.env` (already scaffolded) with:
   - `CLOUDFLARE_API_TOKEN` (required)
   - `CLOUDFLARE_ACCOUNT_ID` (required)
2. Optional:
   - `CLOUDFLARE_R2_BUCKET_FILTER` to report only one bucket.
   - `CLOUDFLARE_GRAPHQL_ENDPOINT` (defaults to `https://api.cloudflare.com/client/v4/graphql`).

## Run

```bash
go run .
```
