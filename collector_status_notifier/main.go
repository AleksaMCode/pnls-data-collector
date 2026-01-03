package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	firebase "firebase.google.com/go/v4"
	"firebase.google.com/go/v4/db"
	"github.com/joho/godotenv"
	"google.golang.org/api/option"
	"gopkg.in/natefinch/lumberjack.v2"
)

var (
	MATTERMOST_WEBHOOK_URL string
	FIREBASE_DATABASE_URL  string
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		log.Fatal("Error loading .env file")
		os.Exit(1)
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	FIREBASE_DATABASE_URL = os.Getenv("FIREBASE_DATABASE_URL")
}

func initLogging() {
	log.SetOutput(&lumberjack.Logger{
		Filename:   "consumer_status_notifier.log",
		MaxSize:    1_000, // Max size in MB before rotating
		MaxBackups: 3,
		MaxAge:     28,
		Compress:   true,
	})
}

func main() {
	loadEnvVariables()
	initLogging()

	absPath, err := getAbsoluteFirebasePath(FIREBASE_CREDENTIALS_FILE)
	if err != nil {
		log.Fatalf("Error getting absolute path for credentials file: %v", err)
	}

	ctx := context.Background()
	opt := option.WithCredentialsFile(absPath)
	conf := &firebase.Config{
		DatabaseURL: FIREBASE_DATABASE_URL,
	}
	app, err := firebase.NewApp(ctx, conf, opt)
	if err != nil {
		log.Fatalf("Error initializing Firebase app: %v", err)
	}

	// Get a reference to the Realtime Database
	client, err := app.Database(ctx)
	if err != nil {
		log.Print(FIREBASE_DATABASE_URL)
		log.Fatalf("Error getting database client: %v", err)
	}

	// Periodically check the Firebase database every `FIREBASE_TIMEOUT` minutes
	ticker := time.NewTicker(FIREBASE_TIMEOUT * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		log.Println("Checking devices status...")
		checkFirebaseAndSendMessage(client, ctx)
	}
}

func getAbsoluteFirebasePath(credentialsFile string) (string, error) {
	absPath, err := filepath.Abs(credentialsFile)
	if err != nil {
		return "", fmt.Errorf("failed to get current directory: %v", err)
	}
	return absPath, nil
}

func checkFirebaseAndSendMessage(client *db.Client, ctx context.Context) {
	// Get today's date in YYYY-MM-DD format (for the device nodes)
	today := time.Now().Format(strings.Split(TIMESTAMP_FORMAT, " ")[0])

	ref := client.NewRef(FIREBASE_BASE_PATH)

	// Get the data from Firebase (this fetches all top-level nodes, which are the devices)
	// TODO Update this so it only fetches needed nodes instead of all
	var rootData map[string]any
	if err := ref.Get(ctx, &rootData); err != nil {
		log.Printf("Error fetching root data from Firebase: %v", err)
		return
	}

	// Iterate through each device node (e.g., RPI-1-2026-01-02)
	for deviceKey, deviceData := range rootData {
		// Check if the device key contains today's date and is from a known device
		if !validateFirebaseNode(deviceKey, today) {
			continue
		}

		deviceMap, _ := deviceData.(map[string]any)
		status, _ := deviceMap["status"].(map[string]any)
		timestamp, _ := status["timestamp"].(string)
		timestampTime, _ := time.Parse(TIMESTAMP_FORMAT, timestamp)
		deviceName := deviceKey[:5]

		// Check if the timestamp is older than `FIREBASE_TIMEOUT` minutes
		// Devices update status every 10 minutes and we check every 11 minutes so have a buffer of 60 seconds just in case
		if time.Since(timestampTime) > FIREBASE_TIMEOUT*time.Minute {
			message := fmt.Sprintf("Device %s hasn't been updated in the last %d minutes! Last update: %s", deviceName, FIREBASE_TIMEOUT, timestamp)
			log.Print(message)
			sendMattermostMessage(message)
		} else {
			log.Printf("Device %s was recently updated at %s", deviceName, timestamp)
		}
	}
}

func validateFirebaseNode(deviceKey, today string) bool {
	if deviceKey == "" || today == "" {
		return false
	}

	// Check if the device key ends with today's date in the format YYYY-MM-DD
	if len(deviceKey) > len(today) && deviceKey[len(deviceKey)-len(today):] == today {
		// Check if the deviceKey contains any of the device names
		for _, device := range Devices {
			if strings.Contains(deviceKey, device) {
				return true
			}
		}
	}
	return false
}

func sendMattermostMessage(message string) {
	payload := map[string]any{
		"text":     message,
		"username": "Collector status notifier",
		// Use Gopher as a bot icon
		"icon_url": "https://raw.githubusercontent.com/golang-samples/gopher-vector/refs/heads/master/gopher.svg",
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
