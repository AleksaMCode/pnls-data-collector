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
		Filename:   LOG_FILE,
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

	// Check Firebase usage
	checkUsage(client, ctx)
}

func getAbsoluteFirebasePath(credentialsFile string) (string, error) {
	absPath, err := filepath.Abs(credentialsFile)
	if err != nil {
		return "", fmt.Errorf("failed to get current directory: %v", err)
	}
	return absPath, nil
}

func bytesToMB(bytes int) float64 {
	return float64(bytes) / (1024 * 1024)
}

func getNodeSize(v any) (float64, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return 0, err
	}
	return float64(bytesToMB(len(b))), nil
}

func checkUsage(client *db.Client, ctx context.Context) {
	ref := client.NewRef(FIREBASE_BASE_PATH)

	var rootData map[string]any
	if err := ref.Get(ctx, &rootData); err != nil {
		log.Printf("Error fetching root data from Firebase: %v", err)
		return
	}
	usage := 0.0
	for _, deviceData := range rootData {
		size, _ := getNodeSize(deviceData)
		usage += size
	}

	message := fmt.Sprintf("A current Firebase Realtime DB usage is %.2f MB out of 1 GB (%.2f%%).", usage, usage/1_000*100)
	sendMattermostMessage(message)
}

func sendMattermostMessage(message string) {
	payload := map[string]any{
		"text":     message,
		"username": "Firebase limit notifier",
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
