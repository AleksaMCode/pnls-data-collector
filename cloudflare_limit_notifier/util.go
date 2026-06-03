package main

import (
	"fmt"
	"os"

	logging "github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/joho/godotenv"
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		logging.Fatal("Error loading .env file")
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	SENTRY_DSN = os.Getenv("SENTRY_DSN")
	CLOUDFLARE_API_TOKEN = os.Getenv("CLOUDFLARE_API_TOKEN")
	CLOUDFLARE_ACCOUNT_ID = os.Getenv("CLOUDFLARE_ACCOUNT_ID")
	CLOUDFLARE_GRAPHQL_ENDPOINT = os.Getenv("CLOUDFLARE_GRAPHQL_ENDPOINT")
	CLOUDFLARE_R2_BUCKET_FILTER = os.Getenv("CLOUDFLARE_R2_BUCKET_FILTER")

	if CLOUDFLARE_GRAPHQL_ENDPOINT == "" {
		CLOUDFLARE_GRAPHQL_ENDPOINT = DEFAULT_GRAPHQL_ENDPOINT
	}
}

func validateRequiredEnv() error {
	if CLOUDFLARE_API_TOKEN == "" {
		return fmt.Errorf("missing CLOUDFLARE_API_TOKEN")
	}
	if CLOUDFLARE_ACCOUNT_ID == "" {
		return fmt.Errorf("missing CLOUDFLARE_ACCOUNT_ID")
	}
	return nil
}
