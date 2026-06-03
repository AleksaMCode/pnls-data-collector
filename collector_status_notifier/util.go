package main

import (
	"os"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
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
}

func isWorkingHours() bool {
	now := common.GetTimeNow(TIMEZONE)
	hour := now.Hour()
	// Start moved to 6. See #189
	return hour >= 6 && hour < 18
}
