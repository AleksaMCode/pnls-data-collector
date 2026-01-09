package main

import (
	"fmt"
	"log"
	"path/filepath"
	"time"
)

func isWorkingHours() bool {
	location, err := time.LoadLocation(TIMEZONE)
	if err != nil {
		log.Fatalf("Error loading timezone: %v", err)
	}
	now := time.Now().In(location)
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
