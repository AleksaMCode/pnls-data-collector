package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

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
