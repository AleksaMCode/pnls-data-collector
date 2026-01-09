package main

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
)

func sendMattermostMessage(message string, imageURL string) {
	payload := map[string]any{
		"text":     message,
		"username": SERVICE_NAME,
		// Use Gopher as a bot icon
		"icon_url": "https://raw.githubusercontent.com/golang-samples/gopher-vector/refs/heads/master/gopher.svg",
		"attachments": []map[string]any{
			{
				"title":     "Cloudflare R2 bucket hosted chart",
				"text":      "Pie chart Firebase Realtime DB usage",
				"color":     "#FF5733",
				"image_url": imageURL,
			},
		},
	}

	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		log.Fatalf("Failed to marshal message: %v", err)
	}

	req, err := http.NewRequest("POST", MATTERMOST_WEBHOOK_URL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		log.Fatalf("Failed to create HTTP request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
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
