package main

import (
	"strings"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// useUnreachableR2 points the uploads at a server that refuses connections, and makes the SDK try only once.
func useUnreachableR2(t *testing.T) {
	t.Helper()

	restoreConfig(t)
	t.Setenv("AWS_MAX_ATTEMPTS", "1")
	R2_ENDPOINT = testutil.RefusedURL()
	R2_ACCESS_KEY, R2_SECRET_KEY = "access-key", "secret-key"
	R2_BUCKET_NAME, R2_BUCKET_PUBLIC_URL = "pnls-charts", "https://pub-charts.r2.dev"
}

func TestR2StoreConfigUsesTheAccount(t *testing.T) {
	restoreConfig(t)
	R2_ENDPOINT, CLOUDFLARE_ACCOUNT_ID = "", "0123abcd"
	R2_ACCESS_KEY, R2_SECRET_KEY = "access-key", "secret-key"
	R2_BUCKET_NAME, R2_BUCKET_PUBLIC_URL = "pnls-charts", "https://pub-charts.r2.dev"

	want := objectstore.Config{
		Endpoint:  "https://0123abcd.r2.cloudflarestorage.com",
		AccessKey: "access-key",
		SecretKey: "secret-key",
		Region:    objectstore.R2Region,
		Bucket:    "pnls-charts",
		PublicURL: "https://pub-charts.r2.dev",
	}
	if got := r2StoreConfig(); got != want {
		t.Fatalf("r2StoreConfig() = %+v, want %+v", got, want)
	}
}

func TestR2StoreConfigPrefersTheCustomEndpoint(t *testing.T) {
	restoreConfig(t)
	R2_ENDPOINT, CLOUDFLARE_ACCOUNT_ID = "http://localhost:9000", "0123abcd"

	got := r2StoreConfig()

	if got.Endpoint != "http://localhost:9000" || !got.UsePathStyle {
		t.Fatalf("expected the custom endpoint with path-style requests, got %+v", got)
	}
}

func TestChartsArePublicPNGs(t *testing.T) {
	if chartUploadOptions.ContentType != "image/png" || chartUploadOptions.ACL != "public-read" {
		t.Fatalf("unexpected upload options %+v", chartUploadOptions)
	}
}

func TestUploadImageToR2ReturnsTheError(t *testing.T) {
	useUnreachableR2(t)

	publicURL, err := uploadImageToR2([]byte("png"))

	if err == nil {
		t.Fatalf("expected an error, got the link %q", publicURL)
	}
	if publicURL != "" {
		t.Errorf("expected no link with the error, got %q", publicURL)
	}
	if !strings.Contains(err.Error(), "failed to upload firebase-limit/firebase-usage-") {
		t.Errorf("expected the failed upload in the error, got %v", err)
	}
}

func TestUploadImageToR2WithoutBucketReturnsTheError(t *testing.T) {
	useUnreachableR2(t)
	R2_BUCKET_NAME = ""

	if _, err := uploadImageToR2([]byte("png")); err == nil || !strings.Contains(err.Error(), "bucket is empty") {
		t.Fatalf("expected the missing bucket as an error, got %v", err)
	}
}
