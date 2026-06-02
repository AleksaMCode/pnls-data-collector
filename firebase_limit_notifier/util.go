package main

import (
	"encoding/json"
	"os"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/joho/godotenv"
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		logging.Fatal("Error loading .env file")
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	FIREBASE_DATABASE_URL = os.Getenv("FIREBASE_DATABASE_URL")
	SENTRY_DSN = os.Getenv("SENTRY_DSN")

	R2_ACCESS_KEY = os.Getenv("R2_ACCESS_KEY")
	R2_SECRET_KEY = os.Getenv("R2_SECRET_KEY")
	R2_BUCKET_NAME = os.Getenv("R2_BUCKET_NAME")
	CLOUDFLARE_ACCOUNT_ID = os.Getenv("CLOUDFLARE_ACCOUNT_ID")
	R2_BUCKET_PUBLIC_URL = os.Getenv("R2_BUCKET_PUBLIC_URL")
	R2_ENDPOINT = os.Getenv("R2_ENDPOINT")
}

func bytesToMB(bytes int) float64 {
	return float64(bytes) / BYTES_IN_MB
}

func getNodeSize(v any) (float64, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return 0, err
	}
	return float64(bytesToMB(len(b))), nil
}
