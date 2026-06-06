package main

import (
	"context"
	"log"
	"time"

	"firebase.google.com/go/v4/db"
	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
)

func main() {
	loadEnvVariables()
	logging.InitObservability(LOG_FILE, SENTRY_DSN, SERVICE_NAME)

	ctx := context.Background()
	client := firebase.GetFirebaseClient(ctx, FIREBASE_CREDENTIALS_FILE, FIREBASE_DATABASE_URL)

	// Check before sleep
	checkDevicesStatus(client, ctx)

	// Periodically check Datadog heartbeat data every `COLLECTOR_TIMEOUT` minutes.
	ticker := time.NewTicker(COLLECTOR_TIMEOUT)
	defer ticker.Stop()

	for range ticker.C {
		checkDevicesStatus(client, ctx)
	}
}

func checkDevicesStatus(client *db.Client, ctx context.Context) {
	log.Println("Checking devices status via Datadog...")
	if err := validateDatadogDeviceData(ctx); err != nil {
		log.Printf("Datadog status check failed, falling back to Firebase status: %v", err)
		validateFirebaseDeviceData(client, ctx)
	}
}
