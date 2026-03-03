package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"firebase.google.com/go/v4/db"
	common "github.com/AleksaMCode/pnls-data-collector/util-go/common"
	firebase "github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	mattermost "github.com/AleksaMCode/pnls-data-collector/util-go/mattermost"
)

func main() {
	loadEnvVariables()
	initLogging()

	ctx := context.Background()
	client := firebase.GetFirebaseClient(ctx, FIREBASE_CREDENTIALS_FILE, FIREBASE_DATABASE_URL)

	// Check Firebase usage
	usage := checkUsage(client, ctx)
	// Create a pie chart and send a Mattermost usage message
	createUsageChart(usage)
}

func checkUsage(client *db.Client, ctx context.Context) float64 {
	ref := client.NewRef(FIREBASE_BASE_PATH)
	usage := 0.0

	// Iterate dates from first of the month until today
	today := common.GetTimeNow(TIMEZONE)
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

	return usage
}

func createUsageChart(usage float64) {
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

	message := fmt.Sprintf(
		"Current Firebase Realtime DB usage is %.2f MB out of 1 GB (%.2f%%).",
		usage,
		getPercentage(usage, FIREBASE_LIMIT_MB),
	)
	sendMattermostMsg(message, publicURL)
}

func sendMattermostMsg(message string, publicURL string) {
	log.Print(message)
	mattermost.SendMattermostMessageWithImage(MATTERMOST_WEBHOOK_URL, SERVICE_NAME, message, publicURL)
}
