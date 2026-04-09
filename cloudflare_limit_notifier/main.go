package main

import (
	"log"

	common "github.com/AleksaMCode/pnls-data-collector/util-go/common"
	mattermost "github.com/AleksaMCode/pnls-data-collector/util-go/mattermost"
	"golang.org/x/text/language"
	"golang.org/x/text/message"
)

func main() {
	loadEnvVariables()
	initLogging()
	if err := validateRequiredEnv(); err != nil {
		log.Fatalf("Invalid configuration: %v", err)
		return
	}

	now := common.GetTimeNow(TIMEZONE)
	client := newCloudflareClient()

	usage, err := client.getCurrentMonthUsage(now)
	if err != nil {
		log.Fatalf("Failed to fetch Cloudflare R2 metrics: %v", err)
		return
	}

	sendUsageReport(usage)
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
