package mattermost

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
)

const botIconURL = "https://raw.githubusercontent.com/golang-samples/gopher-vector/refs/heads/master/gopher.svg"

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
		"icon_url": botIconURL,
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
