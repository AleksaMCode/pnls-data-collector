package main

import (
	"context"
	"fmt"
	"log"

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

	var rootData map[string]any
	if err := ref.Get(ctx, &rootData); err != nil {
		log.Printf("Error fetching root data from Firebase: %v", err)
		return
	}
	usage := 0.0
	for _, deviceData := range rootData {
		size, _ := getNodeSize(deviceData)
		usage += size
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
		log.Printf("Image with a pbulic Cloudflare R2 bucket link was created: %s", publicURL)
	}
	message := fmt.Sprintf("Current Firebase Realtime DB usage is %.2f MB out of 1 GB (%.2f%%).", usage, getPercentage(usage, FIREBASE_LIMIT_MB))
	sendMattermostMessage(message, publicURL)
}
