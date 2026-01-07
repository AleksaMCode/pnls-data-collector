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
)
