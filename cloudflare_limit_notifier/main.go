package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/mattermost"
	"golang.org/x/text/language"
	"golang.org/x/text/message"
)

func main() {
	loadEnvVariables()
	logging.InitObservability(LOG_FILE, SENTRY_DSN, SERVICE_NAME)

	if err := validateRequiredEnv(); err != nil {
		logging.Fatal(fmt.Sprintf("Invalid configuration: %v", err))
		return
	}

	http.HandleFunc(CHECK_ENDPOINT_PATH, checkCloudflareUsageAndNotifyHandler)
	log.Printf("%s listening on :%s%s", SERVICE_NAME, HTTP_PORT, CHECK_ENDPOINT_PATH)

	if err := http.ListenAndServe(":"+HTTP_PORT, nil); err != nil {
		logging.Fatal(fmt.Sprintf("HTTP server failed: %v", err))
	}
}

func checkCloudflareUsageAndNotifyHandler(responseWriter http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		http.Error(responseWriter, "Only POST method is allowed", http.StatusMethodNotAllowed)
		return
	}

	now := common.GetTimeNow(TIMEZONE)
	client := newCloudflareClient()

	usage, err := client.getCurrentMonthUsage(now)
	if err != nil {
		log.Printf("Failed to fetch Cloudflare R2 metrics: %v", err)
		http.Error(responseWriter, "Failed to fetch Cloudflare R2 metrics", http.StatusInternalServerError)
		return
	}

	sendUsageReport(usage)
	responseWriter.WriteHeader(http.StatusOK)
	if _, err := responseWriter.Write([]byte("Cloudflare usage check sent to Mattermost info channel.")); err != nil {
		log.Printf("Failed to write response body: %v", err)
	}
}

func sendUsageReport(usage usageMetrics) {
	storageGB := usage.StorageBytes / BYTES_IN_GB

	printer := message.NewPrinter(language.English)
	message := printer.Sprintf(
		"R2 monthly usage:\n* Storage: %.2f GB / %d GB (%.2f%%)\n* Operations:\n  - Class A: %.0f / %.0f (%.2f%%)\n  - Class B: %.0f / %.0f (%.2f%%)",
		storageGB,
		FREE_TIER_STORAGE_GB,
		common.GetPercentage(storageGB, FREE_TIER_STORAGE_GB),
		usage.ClassARequests,
		FREE_TIER_CLASS_A,
		common.GetPercentage(usage.ClassARequests, FREE_TIER_CLASS_A),
		usage.ClassBRequests,
		FREE_TIER_CLASS_B,
		common.GetPercentage(usage.ClassBRequests, FREE_TIER_CLASS_B),
	)

	log.Print(message)
	mattermost.SendMattermostMessage(MATTERMOST_WEBHOOK_URL, SERVICE_NAME, message)
}
