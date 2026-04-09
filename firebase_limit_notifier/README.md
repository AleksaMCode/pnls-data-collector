# Firebase Limit Notifier (`firebase_limit_notifier`)

`firebase_limit_notifier` is a microservice that estimates current-month Firebase Realtime Database usage, compares it to the free-tier limit, generates a pie chart, uploads the chart to Cloudflare R2, and sends a Mattermost notification.

Current implementation includes:

- monthly usage calculation from Firebase Realtime DB data
  - date-based nodes for `RPI-1`, `RPI-2`, and `RPI-3`
  - additional `/stats` node usage
- pie chart generation in memory
  - chart upload to Cloudflare R2 (public URL)
- Mattermost message with image attachment

## Free-tier limit

- Realtime DB storage: `1 GB` (`1000 MB`)

## Setup

1. Copy/fill `.env` (see `.env.template`) with:
   - `MATTERMOST_WEBHOOK_URL`
   - `FIREBASE_DATABASE_URL`
   - `R2_ACCESS_KEY`
   - `R2_SECRET_KEY`
   - `R2_BUCKET_NAME`
   - `CLOUDFLARE_ACCOUNT_ID`
   - `R2_BUCKET_PUBLIC_URL`
2. Copy `firebase_credentials.json.template` to `firebase_credentials.json` and fill service-account credentials.
3. Optional:
   - `R2_ENDPOINT` for custom endpoint/testing environments.

## Run

```bash
go run .
```

> [!NOTE] 
> 
> If chart generation/upload fails, the notifier still sends the usage message.
