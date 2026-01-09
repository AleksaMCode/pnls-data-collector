package main

import (
	"context"
	"log"
	"os"
	"strings"

	firebase "firebase.google.com/go/v4"
	"firebase.google.com/go/v4/db"
	"google.golang.org/api/option"
)

func getFirebaseClient(ctx context.Context) *db.Client {
	absPath, err := getAbsoluteFirebasePath(FIREBASE_CREDENTIALS_FILE)
	if err != nil {
		log.Fatalf("Error getting absolute path for credentials file: %v", err)
		os.Exit(1)
	}

	opt := option.WithCredentialsFile(absPath)
	conf := &firebase.Config{
		DatabaseURL: FIREBASE_DATABASE_URL,
	}
	app, err := firebase.NewApp(ctx, conf, opt)
	if err != nil {
		log.Fatalf("Error initializing Firebase app: %v", err)
		os.Exit(1)
	}

	// Get a reference to the Realtime Database
	client, err := app.Database(ctx)
	if err != nil {
		log.Fatalf("Error getting database client: %v", err)
		os.Exit(1)
	}

	return client
}

func validateFirebaseNode(deviceKey, today string) bool {
	if deviceKey == "" || today == "" {
		return false
	}

	// Check if the device key ends with today's date in the format YYYY-MM-DD
	if len(deviceKey) > len(today) && deviceKey[len(deviceKey)-len(today):] == today {
		// Check if the deviceKey contains any of the device names
		for _, device := range Devices {
			if strings.Contains(deviceKey, device) {
				return true
			}
		}
	}
	return false
}
