package main

const (
	SERVICE_NAME = "Cloudflare limit notifier"
	LOG_FILE     = "cloudflare_limit_notifier.log"
	TIMEZONE     = "Europe/Paris"

	DEFAULT_GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"
	GRAPHQL_LIMIT            = 1000

	BYTES_IN_GB = 1024 * 1024 * 1024

	// Cloudflare R2 free-tier limits (monthly).
	FREE_TIER_STORAGE_GB = 10
	FREE_TIER_CLASS_A    = 1_000_000.0
	FREE_TIER_CLASS_B    = 10_000_000.0
)

var (
	MATTERMOST_WEBHOOK_URL      string
	CLOUDFLARE_API_TOKEN        string
	CLOUDFLARE_ACCOUNT_ID       string
	CLOUDFLARE_GRAPHQL_ENDPOINT string
	CLOUDFLARE_R2_BUCKET_FILTER string
)
