package main

const (
	SERVICE_NAME = "Cloudflare limit notifier"
	LOG_FILE     = "cloudflare_limit_notifier.log"
	TIMEZONE     = "Europe/Paris"

	DEFAULT_GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"
	GRAPHQL_LIMIT            = 1000
	DEFAULT_RETRY_ATTEMPTS   = 5
	DEFAULT_RETRY_DELAY_SEC  = 1
	DEFAULT_RETRY_MAX_SEC    = 30

	BYTES_IN_GB = 1024 * 1024 * 1024

	// Cloudflare R2 free-tier limits (monthly).
	FREE_TIER_STORAGE_GB = 10
	FREE_TIER_CLASS_A    = 1_000_000.0
	FREE_TIER_CLASS_B    = 10_000_000.0
)

var (
	MATTERMOST_WEBHOOK_URL      string
	SENTRY_DSN                  string
	CLOUDFLARE_API_TOKEN        string
	CLOUDFLARE_ACCOUNT_ID       string
	CLOUDFLARE_GRAPHQL_ENDPOINT string
	CLOUDFLARE_R2_BUCKET_FILTER string
	GRAPHQL_RETRY_ATTEMPTS      uint
	GRAPHQL_RETRY_DELAY         int
	GRAPHQL_RETRY_MAX_DELAY     int
)
