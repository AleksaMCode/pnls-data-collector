package mattermost

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
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

// webhookStatusError is returned when Mattermost answers with a status code other than 200.
type webhookStatusError struct {
	status string
}

func (e *webhookStatusError) Error() string {
	return "Mattermost webhook response: " + e.status
}

// SendMattermostMessage sends a message and terminates the process if the message can't be delivered to Mattermost.
// Long-running services that must stay available should use TrySendMattermostMessage instead.
func SendMattermostMessage(webhookURL string, serviceName string, message string) {
	exitOnDeliveryFailure(postMattermostMessage(webhookURL, serviceName, message, ""))
}

// SendMattermostMessageWithImage sends a message with an image attachment and terminates the process if the message
// can't be delivered to Mattermost. Long-running services that must stay available should use
// TrySendMattermostMessageWithImage instead.
func SendMattermostMessageWithImage(webhookURL string, serviceName string, message string, imageURL string) {
	exitOnDeliveryFailure(postMattermostMessage(webhookURL, serviceName, message, imageURL))
}

// TrySendMattermostMessage sends a message and returns an error, instead of terminating the process, if the message
// can't be delivered or Mattermost doesn't answer with status 200.
func TrySendMattermostMessage(webhookURL string, serviceName string, message string) error {
	return postMattermostMessage(webhookURL, serviceName, message, "")
}

// TrySendMattermostMessageWithImage sends a message with an image attachment and returns an error, instead of
// terminating the process, if the message can't be delivered or Mattermost doesn't answer with status 200.
func TrySendMattermostMessageWithImage(webhookURL string, serviceName string, message string, imageURL string) error {
	return postMattermostMessage(webhookURL, serviceName, message, imageURL)
}

// exitOnDeliveryFailure keeps the behavior of the Send functions: an unexpected status code is only logged, while
// any other failure terminates the process.
func exitOnDeliveryFailure(err error) {
	if err == nil {
		return
	}

	var statusErr *webhookStatusError
	if errors.As(err, &statusErr) {
		log.Print(statusErr.Error())
		return
	}
	log.Fatal(err.Error())
}

func postMattermostMessage(webhookURL string, serviceName string, message string, imageURL string) error {
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
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	req, err := http.NewRequest("POST", webhookURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send message to Mattermost: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return &webhookStatusError{status: resp.Status}
	}

	log.Println("Successfully sent message to Mattermost!")
	return nil
}
