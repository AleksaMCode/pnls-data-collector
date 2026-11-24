package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// useTestConfig points the handler at a readable path and the given Mattermost webhook for the duration of a test.
func useTestConfig(t *testing.T, webhookURL string) {
	t.Helper()

	originalWebhookURL, originalMountPath := MATTERMOST_WEBHOOK_URL, DISK_MOUNT_PATH
	t.Cleanup(func() { MATTERMOST_WEBHOOK_URL, DISK_MOUNT_PATH = originalWebhookURL, originalMountPath })

	MATTERMOST_WEBHOOK_URL = webhookURL
	DISK_MOUNT_PATH = t.TempDir()
}

func TestCheckDiskAndNotifyHandlerRejectsNonPost(t *testing.T) {
	recorder := httptest.NewRecorder()
	checkDiskAndNotifyHandler(recorder, httptest.NewRequest(http.MethodGet, "/check", nil))

	if recorder.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusMethodNotAllowed)
	}
}

func TestCheckDiskAndNotifyHandlerSendsReport(t *testing.T) {
	reports := 0
	mattermostServer := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { reports++ }))
	defer mattermostServer.Close()
	useTestConfig(t, mattermostServer.URL)

	recorder := httptest.NewRecorder()
	checkDiskAndNotifyHandler(recorder, httptest.NewRequest(http.MethodPost, "/check", nil))

	if recorder.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusOK)
	}
	if reports != 1 {
		t.Errorf("reports sent = %d, want 1", reports)
	}
}

func TestCheckDiskAndNotifyHandlerReportsMattermostFailure(t *testing.T) {
	mattermostServer := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	refusedURL := mattermostServer.URL
	mattermostServer.Close()
	useTestConfig(t, refusedURL)

	// The handler must answer with an error and keep serving requests when Mattermost refuses the connection
	for attempt := 1; attempt <= 2; attempt++ {
		recorder := httptest.NewRecorder()
		checkDiskAndNotifyHandler(recorder, httptest.NewRequest(http.MethodPost, "/check", nil))

		if recorder.Code != http.StatusBadGateway {
			t.Errorf("attempt %d: status = %d, want %d", attempt, recorder.Code, http.StatusBadGateway)
		}
	}
}
