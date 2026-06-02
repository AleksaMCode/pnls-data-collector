package main

const (
	SERVICE_NAME              = "Firebase limit notifier"
	FIREBASE_CREDENTIALS_FILE = "firebase_credentials.json"
	FIREBASE_BASE_PATH        = "/"
	LOG_FILE                  = "firebase_limit_notifier.log"
	R2_BUCKET_DIR             = "firebase-limit"
	TIMEZONE                  = "Europe/Paris"
	// Free tier has 1 GB limit on Realtime DB
	FIREBASE_LIMIT_MB = 1_000

	BYTES_IN_MB = 1024 * 1024
)

var (
	MATTERMOST_WEBHOOK_URL string
	FIREBASE_DATABASE_URL  string
	SENTRY_DSN             string
	R2_ACCESS_KEY          string
	R2_SECRET_KEY          string
	R2_BUCKET_NAME         string
	CLOUDFLARE_ACCOUNT_ID  string
	R2_BUCKET_PUBLIC_URL   string
	R2_ENDPOINT            string
)

const (
	DEVICE_RPI_1 = "RPI-1"
	DEVICE_RPI_2 = "RPI-2"
	DEVICE_RPI_3 = "RPI-3"
)

var Devices = []string{DEVICE_RPI_1, DEVICE_RPI_2, DEVICE_RPI_3}
