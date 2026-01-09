package main

import (
	"context"
	"log"
	"os"

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
