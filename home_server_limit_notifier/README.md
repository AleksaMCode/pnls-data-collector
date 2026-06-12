# Home Server Limit Notifier (`home_server_limit_notifier`)

`home_server_limit_notifier` is a Go microservice that exposes an HTTP endpoint for on-demand memory usage checks.

When triggered, it:

- reads filesystem usage for a configured mount path
- computes used/free/total storage and usage percentage
- sends a plain-text report to Mattermost
- returns `200 OK` to the caller on success

## Setup

1. Copy `.env.template` to `.env`.
2. Fill required values.

## Run

```bash
go run .
```

## Trigger check

```bash
curl -X POST http://localhost:<HTTP_PORT><CHECK_ENDPOINT_PATH>
```
