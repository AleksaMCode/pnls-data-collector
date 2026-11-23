package main

import (
	"fmt"
	"log"
	"net/http"

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

	http.HandleFunc(CHECK_ENDPOINT_PATH, checkDiskAndNotifyHandler)
	log.Printf("%s listening on :%s%s", SERVICE_NAME, HTTP_PORT, CHECK_ENDPOINT_PATH)

	if err := http.ListenAndServe(":"+HTTP_PORT, nil); err != nil {
		logging.Fatal(fmt.Sprintf("HTTP server failed: %v", err))
	}
}

func checkDiskAndNotifyHandler(responseWriter http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		http.Error(responseWriter, "Only POST method is allowed", http.StatusMethodNotAllowed)
		return
	}

	usage, err := getDiskUsage(DISK_MOUNT_PATH)
	if err != nil {
		log.Printf("Disk usage check failed: %v", err)
		http.Error(responseWriter, "Failed to check disk usage", http.StatusInternalServerError)
		return
	}

	message := formatUsageMessage(usage, DISK_MOUNT_PATH)
	log.Print(message)
	// A failed report is returned as an HTTP error, so the service stays available for the next check
	if err := mattermost.TrySendMattermostMessage(MATTERMOST_WEBHOOK_URL, SERVICE_NAME, message); err != nil {
		log.Printf("Failed to send disk usage report to Mattermost: %v", err)
		http.Error(responseWriter, "Failed to send disk usage report to Mattermost", http.StatusBadGateway)
		return
	}

	responseWriter.WriteHeader(http.StatusOK)
	if _, err := responseWriter.Write([]byte("Disk usage check sent to Mattermost info channel.")); err != nil {
		log.Printf("Failed to write response body: %v", err)
	}
}
