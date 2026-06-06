package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"firebase.google.com/go/v4/db"
)

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

func validateFirebaseDeviceData(client *db.Client, ctx context.Context) {
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

		// Firebase is a backup source when Datadog query fails.
		if time.Since(timestampTime) > FIREABASE_TIMEOUT {
			message := fmt.Sprintf(
				"Device `%s` hasn't been updated in the last %s! Last update: %s",
				device,
				DATADOG_TIMEOUT.String(),
				timestamp,
			)
			sendMattermostMsg(message)
		} else {
			log.Printf("Device `%s` was recently updated at %s", device, timestamp)
		}
	}
}
