package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func useTestWebhook(t *testing.T, webhookURL string) {
	t.Helper()

	originalWebhookURL := MATTERMOST_WEBHOOK_URL
	t.Cleanup(func() { MATTERMOST_WEBHOOK_URL = originalWebhookURL })
	MATTERMOST_WEBHOOK_URL = webhookURL
}

func TestCheckCloudflareUsageAndNotifyHandlerRejectsNonPost(t *testing.T) {
	recorder := httptest.NewRecorder()
	checkCloudflareUsageAndNotifyHandler(recorder, httptest.NewRequest(http.MethodGet, CHECK_PATH, nil))

	if recorder.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusMethodNotAllowed)
	}
}

func TestSendUsageReportSendsReport(t *testing.T) {
	reports := 0
	mattermostServer := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { reports++ }))
	defer mattermostServer.Close()
	useTestWebhook(t, mattermostServer.URL)

	if err := sendUsageReport(usageMetrics{}); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if reports != 1 {
		t.Errorf("reports sent = %d, want 1", reports)
	}
}

func TestSendUsageReportReturnsMattermostFailure(t *testing.T) {
	mattermostServer := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	refusedURL := mattermostServer.URL
	mattermostServer.Close()
	useTestWebhook(t, refusedURL)

	if err := sendUsageReport(usageMetrics{}); err == nil {
		t.Fatal("expected an error when Mattermost refuses the connection, got nil")
	}
}

func TestSendUsageReportReturnsErrorOnNon200(t *testing.T) {
	mattermostServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer mattermostServer.Close()
	useTestWebhook(t, mattermostServer.URL)

	if err := sendUsageReport(usageMetrics{}); err == nil {
		t.Fatal("expected an error for a non-200 Mattermost response, got nil")
	}
}
