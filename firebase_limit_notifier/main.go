package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"firebase.google.com/go/v4/db"
)

func main() {
	loadEnvVariables()
	initLogging()

	ctx := context.Background()
	client := getFirebaseClient(ctx)

	// Check Firebase usage
	checkUsage(client, ctx)
}

func checkUsage(client *db.Client, ctx context.Context) {
	ref := client.NewRef(FIREBASE_BASE_PATH)
	usage := 0.0

	// Iterate dates from first of month until today
	today := getTimeNow(TIMEZONE)
	firstOfMonth := time.Date(today.Year(), today.Month(), 1, 0, 0, 0, 0, today.Location())

	for _, device := range Devices {
		for d := firstOfMonth; !d.After(today); d = d.AddDate(0, 0, 1) {
			nodeName := fmt.Sprintf("%s-%04d-%02d-%02d", device, d.Year(), d.Month(), d.Day())

			var nodeData any
			if err := ref.Child(nodeName).Get(ctx, &nodeData); err != nil {
				log.Printf("Error fetching node %s: %v", nodeName, err)
				continue
			}

			size, err := getNodeSize(nodeData)
			if err != nil {
				log.Printf("Error calculating size for node %s: %v", nodeName, err)
				continue
			}

			usage += size
		}
	}

	// Fetch the independent /stats node
	var statsData any
	if err := client.NewRef("/stats").Get(ctx, &statsData); err != nil {
		log.Printf("Error fetching /stats node: %v", err)
	} else {
		statsSize, err := getNodeSize(statsData)
		if err != nil {
			log.Printf("Error calculating size for /stats node: %v", err)
		} else {
			usage += statsSize
		}
	}

	pieChart, err := generatePieChartInMemory(usage, 1_000-usage)
	// If the generating of Pie chart has failed the message should still be sent to the Mattermost channel
	// Same goes for the R2 upload. If the upload fails, the link will be empty.
	publicURL := ""

	if err != nil {
		log.Printf("There was an error generating a pie chart: %v", err)
	} else {
		publicURL, err = uploadImageToR2(pieChart)
		if err != nil {
			log.Printf("There was an error uploading the the chart image to R2: %v", err)
		}
		log.Printf("Image with a public Cloudflare R2 bucket link was created: %s", publicURL)
	}
	message := fmt.Sprintf("Current Firebase Realtime DB usage is %.2f MB out of 1 GB (%.2f%%).", usage, getPercentage(usage, FIREBASE_LIMIT_MB))
	sendMattermostMessage(message, publicURL)
}
