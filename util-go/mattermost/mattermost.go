package mattermost

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
)

const (
	botIconBaseURL      = "https://raw.githubusercontent.com/AleksaMCode/pnls-data-collector/master/resources/bot_icons/"
	defaultIconFilename = "status_notifier.png"
)

var botIconFilenameByService = map[string]string{
	// https://www.flaticon.com/free-icon/limitation_12642584
	"Cloudflare limit notifier":  "limit_notifier.png",
	"Firebase limit notifier":    "limit_notifier.png",
	"Home Server limit notifier": "limit_notifier.png",
	// https://www.flaticon.com/free-icon/login-warning_18841837
	"Collector status notifier": "status_notifier.png",
}

func iconURLForService(serviceName string) string {
	filename, ok := botIconFilenameByService[serviceName]
	if !ok {
		filename = defaultIconFilename
	}
	return botIconBaseURL + filename
}

func SendMattermostMessage(webhookURL string, serviceName string, message string) {
	sendMattermostMessage(webhookURL, serviceName, message, "")
}

func SendMattermostMessageWithImage(webhookURL string, serviceName string, message string, imageURL string) {
	sendMattermostMessage(webhookURL, serviceName, message, imageURL)
}

func sendMattermostMessage(webhookURL string, serviceName string, message string, imageURL string) {
	payload := map[string]any{
		"text":     message,
		"username": serviceName,
		"icon_url": iconURLForService(serviceName),
	}

	// Only add attachment if imageURL is provided
	if imageURL != "" {
		payload["attachments"] = []map[string]any{
			{
				"title":     "Cloudflare R2 bucket hosted chart",
				"text":      "Pie chart Firebase Realtime DB usage",
				"color":     "#FF5733",
				"image_url": imageURL,
			},
		}
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		log.Fatalf("Failed to marshal message: %v", err)
	}

	req, err := http.NewRequest("POST", webhookURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		log.Fatalf("Failed to create HTTP request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Fatalf("Failed to send message to Mattermost: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Mattermost webhook response: %s", resp.Status)
	} else {
		log.Println("Successfully sent message to Mattermost!")
	}
}
