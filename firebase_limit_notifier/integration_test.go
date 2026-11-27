//go:build integration

package main

import (
	"bytes"
	"context"
	"fmt"
	"image/png"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil/containers"
)

// useSilo points the uploads at a new bucket on the shared Silo server, which stands in for Cloudflare R2.
func useSilo(t *testing.T) (*containers.Silo, string) {
	t.Helper()

	silo := containers.StartSilo(t)
	bucket := silo.CreateBucket(t, "firebase-limit")

	restoreConfig(t)
	R2_ENDPOINT = silo.Endpoint
	R2_ACCESS_KEY, R2_SECRET_KEY = containers.SiloAccessKey, containers.SiloSecretKey
	R2_BUCKET_NAME = bucket
	R2_BUCKET_PUBLIC_URL = "https://pub-charts.r2.dev"
	return silo, bucket
}

var chartKeyPattern = regexp.MustCompile(`^firebase-limit/firebase-usage-(\d+)\.png$`)

func TestUploadImageToR2StoresTheChart(t *testing.T) {
	silo, bucket := useSilo(t)
	chart, err := generatePieChartInMemory(250, 750)
	if err != nil {
		t.Fatalf("failed to draw the chart: %v", err)
	}

	before := time.Now().Unix()
	publicURL, err := uploadImageToR2(chart)
	after := time.Now().Unix()
	if err != nil {
		t.Fatalf("uploadImageToR2 returned error: %v", err)
	}

	keys := silo.ListKeys(t, bucket)
	if len(keys) != 1 {
		t.Fatalf("expected one object, got %v", keys)
	}
	match := chartKeyPattern.FindStringSubmatch(keys[0])
	if match == nil {
		t.Fatalf("unexpected key %q", keys[0])
	}
	if uploaded, _ := strconv.ParseInt(match[1], 10, 64); uploaded < before || uploaded > after {
		t.Errorf("expected the upload time in the key, between %d and %d, got %d", before, after, uploaded)
	}
	if publicURL != R2_BUCKET_PUBLIC_URL+"/"+keys[0] {
		t.Errorf("publicURL = %q, want the public bucket URL and the key", publicURL)
	}

	content, contentType := silo.GetObject(t, bucket, keys[0])
	if !bytes.Equal(content, chart) {
		t.Errorf("the stored object isn't the chart: got %d bytes, want %d", len(content), len(chart))
	}
	if contentType != "image/png" {
		t.Errorf("content type = %q, want image/png", contentType)
	}
}

func TestUploadImageToR2KeepsEveryChart(t *testing.T) {
	silo, bucket := useSilo(t)

	first, err := uploadImageToR2([]byte("first"))
	if err != nil {
		t.Fatalf("first upload failed: %v", err)
	}
	// The key has the time in seconds, so a second upload in the same second would replace the first.
	time.Sleep(1100 * time.Millisecond)
	second, err := uploadImageToR2([]byte("second"))
	if err != nil {
		t.Fatalf("second upload failed: %v", err)
	}

	if first == second {
		t.Fatalf("expected two links, got %q twice", first)
	}
	if keys := silo.ListKeys(t, bucket); len(keys) != 2 {
		t.Fatalf("expected both charts in the bucket, got %v", keys)
	}
}

func TestUploadImageToR2MissingBucket(t *testing.T) {
	useSilo(t)
	R2_BUCKET_NAME = "firebase-limit-missing"

	publicURL, err := uploadImageToR2([]byte("png"))
	if err == nil || !strings.Contains(err.Error(), "NoSuchBucket") {
		t.Fatalf("expected a NoSuchBucket error, got the link %q and %v", publicURL, err)
	}
}

func TestUploadImageToR2WrongKeys(t *testing.T) {
	useSilo(t)
	R2_SECRET_KEY = "wrong-secret"

	publicURL, err := uploadImageToR2([]byte("png"))
	if err == nil || !strings.Contains(err.Error(), "SignatureDoesNotMatch") {
		t.Fatalf("expected a signature error, got the link %q and %v", publicURL, err)
	}
}

func TestCreateUsageChartAttachesTheUploadedChart(t *testing.T) {
	silo, bucket := useSilo(t)
	webhook := testutil.NewFakeWebhook(t)
	MATTERMOST_WEBHOOK_URL = webhook.URL()

	if err := createUsageChart(250); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	attachments, _ := webhook.OnlyMessage(t)["attachments"].([]any)
	if len(attachments) != 1 {
		t.Fatalf("expected the chart as an attachment, got %v", webhook.OnlyMessage(t))
	}
	imageURL, _ := attachments[0].(map[string]any)["image_url"].(string)
	key := strings.TrimPrefix(imageURL, R2_BUCKET_PUBLIC_URL+"/")
	if !chartKeyPattern.MatchString(key) {
		t.Fatalf("unexpected image link %q", imageURL)
	}
	content, _ := silo.GetObject(t, bucket, key)
	if _, err := png.DecodeConfig(bytes.NewReader(content)); err != nil {
		t.Fatalf("the linked object isn't a PNG: %v", err)
	}
}

func TestCreateUsageChartOverTheLimitAttachesTheChart(t *testing.T) {
	useSilo(t)
	webhook := testutil.NewFakeWebhook(t)
	MATTERMOST_WEBHOOK_URL = webhook.URL()

	if err := createUsageChart(1200); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	testutil.ExpectFailure(
		t,
		"Over the limit, the chart can't be drawn, so the report has no chart.",
		func(t testutil.TB) {
			if _, ok := webhook.OnlyMessage(t)["attachments"]; !ok {
				t.Error("expected the chart as an attachment")
			}
		},
	)
}

// useEmulator returns a new database on the shared Firebase emulator, with collector data for every other day of the
// month and /stats, and a client the way main makes it.
func useEmulator(t *testing.T) (*containers.FirebaseDatabase, map[string]any) {
	t.Helper()

	database := containers.StartFirebaseEmulator(t).CreateDatabase(t, "fblimnot")
	nodes := map[string]any{"stats": map[string]any{"devices": 3, "networks": 1520}}
	for index, name := range monthNodeNames() {
		if index%2 == 0 {
			nodes[name] = collectorNode(index)
		}
	}
	for name, node := range nodes {
		database.Set(t, name, node)
	}
	return database, nodes
}

func TestCheckUsageAgainstTheEmulator(t *testing.T) {
	database, nodes := useEmulator(t)
	// Data the check doesn't count: last month's node, and another device.
	database.Set(t, lastMonthNodeName(), collectorNode(1))
	database.Set(t, "RPI-4-2026-01-01", collectorNode(2))
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(t), database.URL())

	usage := checkUsage(context.Background(), client)

	if want := usageOf(t, nodes, append(monthNodeNames(), "stats")...); usage != want {
		t.Fatalf("usage = %v MB, want %v MB", usage, want)
	}
}

func TestCheckUsageOfAnEmptyDatabase(t *testing.T) {
	database := containers.StartFirebaseEmulator(t).CreateDatabase(t, "fblimnot-empty")
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(t), database.URL())

	usage := checkUsage(context.Background(), client)

	// Every node reads as null, 4 bytes each.
	if want := usageOf(t, map[string]any{}, append(monthNodeNames(), "stats")...); usage != want {
		t.Fatalf("usage = %v MB, want %v MB", usage, want)
	}
}

func TestMainSendsTheReportWithTheChart(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	database, nodes := useEmulator(t)
	silo, bucket := useSilo(t)
	webhook := testutil.NewFakeWebhook(t)
	port := freePort(t)
	dir := writeServiceFiles(t, database.CredentialsFile(t), map[string]string{
		"MATTERMOST_WEBHOOK_URL": webhook.URL(),
		"FIREBASE_DATABASE_URL":  database.URL(),
		"R2_ENDPOINT":            silo.Endpoint,
		"R2_ACCESS_KEY":          containers.SiloAccessKey,
		"R2_SECRET_KEY":          containers.SiloSecretKey,
		"R2_BUCKET_NAME":         bucket,
		"HTTP_PORT":              port,
	})

	result := runMainInChild(t, dir, "http://localhost:"+port+"/check")

	if !strings.Contains(result.Stdout, fmt.Sprintf("reply: %d ", http.StatusOK)) {
		t.Fatalf("expected the check to succeed, got:\n%s", result.Output())
	}
	message := webhook.OnlyMessage(t)
	usage := usageOf(t, nodes, append(monthNodeNames(), "stats")...)
	want := fmt.Sprintf("Current Firebase Realtime DB usage is %.2f MB out of 1 GB", usage)
	if text, _ := message["text"].(string); !strings.HasPrefix(text, want) {
		t.Errorf("expected the report to start with %q, got %q", want, text)
	}
	if keys := silo.ListKeys(t, bucket); len(keys) != 1 || !chartKeyPattern.MatchString(keys[0]) {
		t.Errorf("expected the chart in the bucket, got %v", keys)
	}
	if _, ok := message["attachments"]; !ok {
		t.Errorf("expected the chart as an attachment, got %v", message)
	}
}
