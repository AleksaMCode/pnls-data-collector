package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

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

func getTimeNow(timezone string) time.Time {
	location, err := time.LoadLocation(timezone)
	if err != nil {
		log.Fatalf("Error loading timezone: %v", err)
		os.Exit(1)
	}

	return time.Now().In(location)
}

func isWorkingHours() bool {
	now := getTimeNow(TIMEZONE)
	hour := now.Hour()
	return hour >= 7 && hour < 18
}

func getAbsoluteFirebasePath(credentialsFile string) (string, error) {
	absPath, err := filepath.Abs(credentialsFile)
	if err != nil {
		return "", fmt.Errorf("failed to get current directory: %v", err)
	}
	return absPath, nil
}
