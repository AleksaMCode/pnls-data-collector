package main

import (
	"fmt"
	"log"
	"os"

	"github.com/joho/godotenv"
	"gopkg.in/natefinch/lumberjack.v2"
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		log.Fatal("Error loading .env file")
		os.Exit(1)
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	CLOUDFLARE_API_TOKEN = os.Getenv("CLOUDFLARE_API_TOKEN")
	CLOUDFLARE_ACCOUNT_ID = os.Getenv("CLOUDFLARE_ACCOUNT_ID")
	CLOUDFLARE_GRAPHQL_ENDPOINT = os.Getenv("CLOUDFLARE_GRAPHQL_ENDPOINT")
	CLOUDFLARE_R2_BUCKET_FILTER = os.Getenv("CLOUDFLARE_R2_BUCKET_FILTER")

	if CLOUDFLARE_GRAPHQL_ENDPOINT == "" {
		CLOUDFLARE_GRAPHQL_ENDPOINT = DEFAULT_GRAPHQL_ENDPOINT
	}
}

func initLogging() {
	log.SetOutput(&lumberjack.Logger{
		Filename:   LOG_FILE,
		MaxSize:    1_000,
		MaxBackups: 3,
		MaxAge:     28,
		Compress:   true,
	})
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
