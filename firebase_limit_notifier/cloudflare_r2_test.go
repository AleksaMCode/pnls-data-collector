package main

import (
	"strings"
	"testing"

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

func TestGetR2EndpointUsesTheAccount(t *testing.T) {
	restoreConfig(t)
	R2_ENDPOINT, CLOUDFLARE_ACCOUNT_ID = "", "0123abcd"

	if got := getR2Endpoint(); got != "https://0123abcd.r2.cloudflarestorage.com" {
		t.Fatalf("getR2Endpoint() = %q", got)
	}
}

func TestGetR2EndpointPrefersTheCustomEndpoint(t *testing.T) {
	restoreConfig(t)
	R2_ENDPOINT, CLOUDFLARE_ACCOUNT_ID = "http://localhost:9000", "0123abcd"

	if got := getR2Endpoint(); got != "http://localhost:9000" {
		t.Fatalf("getR2Endpoint() = %q", got)
	}
}

func TestNewR2ClientUsesPathStyleOnlyForACustomEndpoint(t *testing.T) {
	restoreConfig(t)

	R2_ENDPOINT = ""
	if newR2Client().Options().UsePathStyle {
		t.Error("expected virtual-hosted requests for Cloudflare R2")
	}

	R2_ENDPOINT = "http://localhost:9000"
	options := newR2Client().Options()
	if !options.UsePathStyle {
		t.Error("expected path-style requests for a custom endpoint")
	}
	if options.Region != "auto" {
		t.Errorf("Region = %q, want auto", options.Region)
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
	if !strings.Contains(err.Error(), "PutObject") {
		t.Errorf("expected the failed upload in the error, got %v", err)
	}
}
