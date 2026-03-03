package main

import (
	"log"
	"os"

	common "github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/joho/godotenv"
	"gopkg.in/natefinch/lumberjack.v2"
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		log.Fatal("Error loading .env file")
		os.Exit(1)
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	FIREBASE_DATABASE_URL = os.Getenv("FIREBASE_DATABASE_URL")
}

func initLogging() {
	log.SetOutput(&lumberjack.Logger{
		Filename:   LOG_FILE,
		MaxSize:    1_000, // Max size in MB before rotating
		MaxBackups: 3,
		MaxAge:     28,
		Compress:   true,
	})
}

func isWorkingHours() bool {
	now := common.GetTimeNow(TIMEZONE)
	hour := now.Hour()
	// Start moved to 6. See #189
	return hour >= 6 && hour < 18
}
