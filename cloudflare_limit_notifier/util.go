package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"

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
	HTTP_PORT = strings.TrimSpace(os.Getenv("HTTP_PORT"))
	CHECK_ENDPOINT_PATH = strings.TrimSpace(os.Getenv("CHECK_ENDPOINT_PATH"))

	if CLOUDFLARE_GRAPHQL_ENDPOINT == "" {
		CLOUDFLARE_GRAPHQL_ENDPOINT = DEFAULT_GRAPHQL_ENDPOINT
	}
	if CHECK_ENDPOINT_PATH == "" {
		CHECK_ENDPOINT_PATH = CHECK_PATH
	}
	CHECK_ENDPOINT_PATH = normalizePath(CHECK_ENDPOINT_PATH)

	var err error
	GRAPHQL_RETRY_ATTEMPTS, err = getPositiveUintEnv("CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS", DEFAULT_RETRY_ATTEMPTS)
	if err != nil {
		logging.Fatal(err.Error())
	}
	GRAPHQL_RETRY_DELAY, err = getPositiveIntEnv("CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS", DEFAULT_RETRY_DELAY_SEC)
	if err != nil {
		logging.Fatal(err.Error())
	}
	GRAPHQL_RETRY_MAX_DELAY, err = getPositiveIntEnv(
		"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS",
		DEFAULT_RETRY_MAX_SEC,
	)
	if err != nil {
		logging.Fatal(err.Error())
	}
}

func validateRequiredEnv() error {
	if CLOUDFLARE_API_TOKEN == "" {
		return fmt.Errorf("missing CLOUDFLARE_API_TOKEN")
	}
	if CLOUDFLARE_ACCOUNT_ID == "" {
		return fmt.Errorf("missing CLOUDFLARE_ACCOUNT_ID")
	}
	if HTTP_PORT == "" {
		return fmt.Errorf("missing HTTP_PORT")
	}
	if CHECK_ENDPOINT_PATH == "" {
		return fmt.Errorf("missing CHECK_ENDPOINT_PATH")
	}
	if GRAPHQL_RETRY_MAX_DELAY < GRAPHQL_RETRY_DELAY {
		return fmt.Errorf(
			"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS (%d) must be >= CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS (%d)",
			GRAPHQL_RETRY_MAX_DELAY,
			GRAPHQL_RETRY_DELAY,
		)
	}
	return nil
}

func normalizePath(path string) string {
	trimmedPath := strings.TrimSpace(path)
	if trimmedPath == "" {
		return ""
	}

	if strings.HasPrefix(trimmedPath, "/") {
		return trimmedPath
	}
	return "/" + trimmedPath
}

func getPositiveIntEnv(key string, fallback int) (int, error) {
	raw := os.Getenv(key)
	if raw == "" {
		return fallback, nil
	}

	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer, got %q", key, raw)
	}
	if value <= 0 {
		return 0, fmt.Errorf("%s must be > 0, got %d", key, value)
	}
	return value, nil
}

func getPositiveUintEnv(key string, fallback int) (uint, error) {
	value, err := getPositiveIntEnv(key, fallback)
	if err != nil {
		return 0, err
	}
	return uint(value), nil
}
