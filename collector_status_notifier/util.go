package main

import (
	"log"
	"os"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/mattermost"
	"github.com/joho/godotenv"
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		logging.Fatal("Error loading .env file")
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	FIREBASE_DATABASE_URL = os.Getenv("FIREBASE_DATABASE_URL")
	SENTRY_DSN = os.Getenv("SENTRY_DSN")
	DATADOG_API_KEY = os.Getenv("DATADOG_API_KEY")
	DATADOG_APP_KEY = os.Getenv("DATADOG_APP_KEY")
	DATADOG_HEARTBEAT_METRIC = os.Getenv("DATADOG_HEARTBEAT_METRIC")
	DATADOG_HOST = os.Getenv("DATADOG_HOST")
}

// Deprecated: Shouldn't be used anymore as this service now works all the time. See #296
func isWorkingHours() bool {
	now := common.GetTimeNow(TIMEZONE)
	hour := now.Hour()
	// Start moved to 6. See #189
	return hour >= 6 && hour < 18
}

func sendMattermostMsg(message string) {
	log.Print(message)
	mattermost.SendMattermostMessage(MATTERMOST_WEBHOOK_URL, SERVICE_NAME, message)
}
