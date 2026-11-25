package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"firebase.google.com/go/v4/db"
	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
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

func validateFirebaseDeviceData(ctx context.Context, client *db.Client) {
	// Collectors name the node and stamp the heartbeat in TIMEZONE wall time,
	// so derive today's date (YYYY-MM-DD) and parse timestamps in that zone
	// rather than the container's (UTC).
	now := common.GetTimeNow(TIMEZONE)
	dateFormat, _, _ := strings.Cut(TIMESTAMP_FORMAT, " ")
	today := now.Format(dateFormat)
	yesterday := now.AddDate(0, 0, -1).Format(dateFormat)

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

		// Right after midnight today's node has no status until the device's
		// first heartbeat of the day. Fall back to yesterday's node; the
		// staleness check below still alerts if that heartbeat is old.
		if deviceData == nil {
			prevNodeName := fmt.Sprintf("%s-%s", device, yesterday)
			if err := rootRef.Child(prevNodeName).Child("status").Get(ctx, &deviceData); err != nil {
				log.Printf("Error fetching status for node %s: %v", prevNodeName, err)
				continue
			}
		}

		// Handle the edge case when data is missing.
		if deviceData == nil {
			message := fmt.Sprintf("Device `%s` has no status for today (%s)", device, today)
			processDeviceStatus(ctx, device, true, message)
			continue
		}

		timestamp, _ := deviceData["timestamp"].(string)
		timestampTime, err := time.ParseInLocation(TIMESTAMP_FORMAT, timestamp, now.Location())
		if err != nil {
			message := fmt.Sprintf("Device `%s` has invalid timestamp in Firebase status: %q", device, timestamp)
			processDeviceStatus(ctx, device, true, message)
			continue
		}

		// Firebase is a backup source when Datadog query fails.
		if time.Since(timestampTime) > FIREABASE_TIMEOUT {
			message := fmt.Sprintf(
				"Device `%s` hasn't been updated in the last %s! Last update: %s",
				device,
				FIREABASE_TIMEOUT.String(),
				timestamp,
			)
			processDeviceStatus(ctx, device, true, message)
		} else {
			log.Printf("Device `%s` was recently updated at %s", device, timestamp)
			processDeviceStatus(ctx, device, false, "")
		}
	}
}
