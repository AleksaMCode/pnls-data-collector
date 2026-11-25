package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	"firebase.google.com/go/v4/db"
	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/mattermost"
)

func main() {
	loadEnvVariables()
	logging.InitObservability(LOG_FILE, SENTRY_DSN, SERVICE_NAME)

	if err := validateRequiredEnv(); err != nil {
		logging.Fatal(fmt.Sprintf("Invalid configuration: %v", err))
		return
	}

	ctx := context.Background()
	client := firebase.GetFirebaseClient(ctx, FIREBASE_CREDENTIALS_FILE, FIREBASE_DATABASE_URL)

	http.HandleFunc(CHECK_ENDPOINT_PATH, newCheckFirebaseUsageHandler(func() error {
		// Check Firebase usage
		usage := checkUsage(ctx, client)
		// Create a pie chart and send a Mattermost usage message
		return createUsageChart(usage)
	}))
	log.Printf("%s listening on :%s%s", SERVICE_NAME, HTTP_PORT, CHECK_ENDPOINT_PATH)

	if err := http.ListenAndServe(":"+HTTP_PORT, nil); err != nil {
		logging.Fatal(fmt.Sprintf("HTTP server failed: %v", err))
	}
}

// newCheckFirebaseUsageHandler returns a handler that runs the usage check on every POST request.
// A failed check is reported as an HTTP error, so the service stays available for the next check.
func newCheckFirebaseUsageHandler(runCheck func() error) http.HandlerFunc {
	return func(responseWriter http.ResponseWriter, request *http.Request) {
		if request.Method != http.MethodPost {
			http.Error(responseWriter, "Only POST method is allowed", http.StatusMethodNotAllowed)
			return
		}

		if err := runCheck(); err != nil {
			log.Printf("Firebase usage check failed: %v", err)
			http.Error(responseWriter, "Failed to send Firebase usage report to Mattermost", http.StatusBadGateway)
			return
		}

		responseWriter.WriteHeader(http.StatusOK)
		if _, err := responseWriter.Write([]byte("Firebase usage check sent to Mattermost info channel.")); err != nil {
			log.Printf("Failed to write response body: %v", err)
		}
	}
}

func checkUsage(ctx context.Context, client *db.Client) float64 {
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

func createUsageChart(usage float64) error {
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
		common.GetPercentage(usage, FIREBASE_LIMIT_MB),
	)
	return sendMattermostMsg(message, publicURL)
}

func sendMattermostMsg(message string, publicURL string) error {
	log.Print(message)
	return mattermost.TrySendMattermostMessageWithImage(MATTERMOST_WEBHOOK_URL, SERVICE_NAME, message, publicURL)
}
