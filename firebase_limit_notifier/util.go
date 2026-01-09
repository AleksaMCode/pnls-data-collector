package main

import (
	"encoding/json"
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

	R2_ACCESS_KEY = os.Getenv("R2_ACCESS_KEY")
	R2_SECRET_KEY = os.Getenv("R2_SECRET_KEY")
	R2_BUCKET_NAME = os.Getenv("R2_BUCKET_NAME")
	CLOUDFLARE_ACCOUNT_ID = os.Getenv("CLOUDFLARE_ACCOUNT_ID")
	R2_BUCKET_PUBLIC_URL = os.Getenv("R2_BUCKET_PUBLIC_URL")
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

func bytesToMB(bytes int) float64 {
	return float64(bytes) / (1024 * 1024)
}

func getPercentage(part float64, whole float64) float64 {
	return part / whole * 100
}

func getTimeNow(timezone string) time.Time {
	location, err := time.LoadLocation(timezone)
	if err != nil {
		log.Fatalf("Error loading timezone: %v", err)
		os.Exit(1)
	}

	return time.Now().In(location)
}

func getAbsoluteFirebasePath(credentialsFile string) (string, error) {
	absPath, err := filepath.Abs(credentialsFile)
	if err != nil {
		return "", fmt.Errorf("failed to get current directory: %v", err)
	}
	return absPath, nil
}

func getNodeSize(v any) (float64, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return 0, err
	}
	return float64(bytesToMB(len(b))), nil
}
