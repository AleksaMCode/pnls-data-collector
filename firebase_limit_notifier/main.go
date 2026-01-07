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
	"time"

	firebase "firebase.google.com/go/v4"
	"firebase.google.com/go/v4/db"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/go-analyze/charts"
	"github.com/joho/godotenv"
	"google.golang.org/api/option"
	"gopkg.in/natefinch/lumberjack.v2"
)

var (
	MATTERMOST_WEBHOOK_URL string
	FIREBASE_DATABASE_URL  string
	R2_ACCESS_KEY          string
	R2_SECRET_KEY          string
	R2_BUCKET_NAME         string
	CLOUDFLARE_ACCOUNT_ID  string
	R2_BUCKET_PUBLIC_URL   string
)

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		log.Fatal("Error loading .env file")
		os.Exit(1)
	}

	MATTERMOST_WEBHOOK_URL = os.Getenv("MATTERMOST_WEBHOOK_URL")
	FIREBASE_DATABASE_URL = os.Getenv("FIREBASE_DATABASE_URL")

	R2_ACCESS_KEY = os.Getenv("R2_ACCESS_KEY")
	R2_SECRET_KEY = os.Getenv("R2_SECRET_KEY")
	R2_BUCKET_NAME = os.Getenv("R2_BUCKET_NAME")
	CLOUDFLARE_ACCOUNT_ID = os.Getenv("CLOUDFLARE_ACCOUNT_ID")
	R2_BUCKET_PUBLIC_URL = os.Getenv("R2_BUCKET_PUBLIC_URL")
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
		log.Printf("Image with a pbulic Cloudflare R2 bucket link was created: %s", publicURL)
	}
	message := fmt.Sprintf("Current Firebase Realtime DB usage is %.2f MB out of 1 GB (%.2f%%).", usage, getPercentage(usage, FIREBASE_LIMIT_MB))
	sendMattermostMessage(message, publicURL)
}

func getPercentage(part float64, whole float64) float64 {
	return part / whole * 100
}

func generatePieChartInMemory(used float64, free float64) ([]byte, error) {
	values := []float64{used, free}
	labels := []string{"Used", "Free"}

	p, err := charts.PieRender(values,
		charts.LegendOptionFunc(charts.LegendOption{
			SeriesNames: labels,
		}),
		charts.TitleOptionFunc(charts.TitleOption{
			Text: "PNLS-DC\nFirebase Realtime DB Usage",
		}),
	)
	if err != nil {
		return nil, err
	}

	buf, err := p.Bytes()
	if err != nil {
		return nil, err
	}

	return buf, nil
}

func saveByteArrayToFile(filename string, pieChart []byte) {
	err := os.WriteFile(filename, pieChart, 0o644)
	if err != nil {
		log.Fatalf("Failed to save pie chart: %v", err)
	}
	log.Printf("Pie chart saved to %s", filename)
}

func newR2Client() *s3.Client {
	cfg, err := config.LoadDefaultConfig(
		context.TODO(),
		config.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(
				R2_ACCESS_KEY,
				R2_SECRET_KEY,
				"",
			),
		),
		config.WithRegion("auto"), // Required by SDK but not used by R2
	)
	if err != nil {
		log.Fatal(err)
		return nil
	}

	client := s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(fmt.Sprintf("https://%s.r2.cloudflarestorage.com", CLOUDFLARE_ACCOUNT_ID))
	})
	return client
}

func uploadImageToR2(image []byte) (string, error) {
	client := newR2Client()
	location, err := time.LoadLocation(TIMEZONE)
	if err != nil {
		log.Fatalf("Error loading timezone: %v", err)
		return "", err
	}

	objectKey := fmt.Sprintf(
		"%s/firebase-usage-%d.png",
		R2_BUCKET_DIR,
		time.Now().In(location).Unix(),
	)

	_, err = client.PutObject(context.TODO(), &s3.PutObjectInput{
		Bucket:      &R2_BUCKET_NAME,
		Key:         &objectKey,
		Body:        bytes.NewReader(image),
		ContentType: aws.String("image/png"),
		ACL:         "public-read",
	})
	if err != nil {
		return "", err
	}

	publicURL := fmt.Sprintf(
		"%s/%s",
		R2_BUCKET_PUBLIC_URL,
		objectKey,
	)

	return publicURL, nil
}

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
