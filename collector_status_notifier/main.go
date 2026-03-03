package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"firebase.google.com/go/v4/db"
	firebase "github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	mattermost "github.com/AleksaMCode/pnls-data-collector/util-go/mattermost"
)

func main() {
	loadEnvVariables()
	initLogging()

	ctx := context.Background()
	client := firebase.GetFirebaseClient(ctx, FIREBASE_CREDENTIALS_FILE, FIREBASE_DATABASE_URL)

	// Check before sleep
	if isWorkingHours() {
		checkDevicesStatus(client, ctx)
	}

	// Periodically check the Firebase database every `FIREBASE_TIMEOUT` minutes
	ticker := time.NewTicker(FIREBASE_TIMEOUT * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		if isWorkingHours() {
			checkDevicesStatus(client, ctx)
		}
	}
}

func checkDevicesStatus(client *db.Client, ctx context.Context) {
	log.Println("Checking devices status...")
	validateDeviceData(client, ctx)
}

func validateDeviceData(client *db.Client, ctx context.Context) {
	// Get today's date in YYYY-MM-DD format (for the device nodes)
	today := time.Now().Format(strings.Split(TIMESTAMP_FORMAT, " ")[0])

	rootRef := client.NewRef(FIREBASE_BASE_PATH)

	// Iterate through each device
	for _, device := range Devices {
		// Build node name: RPI-1-2026-01-02
		nodeName := fmt.Sprintf("%s-%s", device, today)

		if !validateFirebaseNode(nodeName, today) {
			log.Printf("The node name `%s` isn't properly formatted.", nodeName)
			continue
		}

		// Only fetch the "status" child, not the whole node (see #105)
		statusRef := rootRef.Child(nodeName).Child("status")

		var deviceData map[string]any
		if err := statusRef.Get(ctx, &deviceData); err != nil {
			log.Printf("Error fetching status for node %s: %v", nodeName, err)
			continue
		}

		// Handle the edge case when data is missing.
		if deviceData == nil {
			message := fmt.Sprintf("Device `%s` has no status for today (%s)", device, today)
			sendMattermostMsg(message)
			continue
		}

		timestamp, _ := deviceData["timestamp"].(string)
		timestampTime, _ := time.Parse(TIMESTAMP_FORMAT, timestamp)

		// Check if the timestamp is older than `FIREBASE_TIMEOUT` minutes
		// Devices update status every 10 minutes and we check every 11 minutes so have a buffer of 60 seconds just in case of some delays
		if time.Since(timestampTime) > FIREBASE_TIMEOUT*time.Minute {
			message := fmt.Sprintf("Device `%s` hasn't been updated in the last %d minutes! Last update: %s", device, FIREBASE_TIMEOUT, timestamp)
			sendMattermostMsg(message)
		} else {
			log.Printf("Device `%s` was recently updated at %s", device, timestamp)
		}
	}
}

func sendMattermostMsg(message string) {
	log.Print(message)
	mattermost.SendMattermostMessage(MATTERMOST_WEBHOOK_URL, SERVICE_NAME, message)
}
