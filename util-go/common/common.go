package common

import (
	"log"
	"os"
	"time"
)

func GetTimeNow(timezone string) time.Time {
	location, err := time.LoadLocation(timezone)
	if err != nil {
		log.Fatalf("Error loading timezone: %v", err)
		os.Exit(1)
	}

	return time.Now().In(location)
}

// func GetAbsoluteFirebasePath(credentialsFile string) (string, error) {
// 	absPath, err := filepath.Abs(credentialsFile)
// 	if err != nil {
// 		return "", fmt.Errorf("failed to get current directory: %v", err)
// 	}
// 	return absPath, nil
// }
