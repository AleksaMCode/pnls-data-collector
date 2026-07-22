package main

import (
	"context"
	"fmt"
	"log"
	"time"
)

func processDeviceStatus(ctx context.Context, device string, isOffline bool, offlineMessage string) {
	now := time.Now().UTC()

	if isOffline {
		isFirstOffline, cached, err := markDeviceOffline(ctx, device, now)
		if err != nil {
			log.Printf("Failed to cache offline status for `%s`: %v", device, err)
			return
		}

		if isFirstOffline {
			sendMattermostMsg(offlineMessage)
			return
		}

		log.Printf(
			"Device `%s` is still offline. First seen: %s, updated at: %s",
			device,
			cached.FirstDiscoveredAt.Format(time.RFC3339),
			cached.UpdatedAt.Format(time.RFC3339),
		)
		return
	}

	cached, wasOffline, err := markDeviceOnline(ctx, device)
	if err != nil {
		log.Printf("Failed to clear offline status for `%s`: %v", device, err)
		return
	}

	if !wasOffline {
		log.Printf("Device `%s` is online and has no offline cache state", device)
		return
	}

	recoveryMessage := fmt.Sprintf(
		"Device `%s` is back online. First offline detected at %s, last offline check at %s",
		device,
		cached.FirstDiscoveredAt.Format(time.RFC3339),
		cached.UpdatedAt.Format(time.RFC3339),
	)
	sendMattermostMsg(recoveryMessage)
}
