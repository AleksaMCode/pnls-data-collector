package mattermost

import (
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
	"testing"
)

func TestSendMattermostMessagePostsExpectedPayload(t *testing.T) {
	var received map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST request, got %s", r.Method)
		}
		if got := r.Header.Get("Content-Type"); got != "application/json" {
			t.Fatalf("expected Content-Type application/json, got %q", got)
		}

		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("failed to read request body: %v", err)
		}

		if err := json.Unmarshal(body, &received); err != nil {
			t.Fatalf("failed to unmarshal payload: %v", err)
		}

		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	SendMattermostMessage(server.URL, "collector-status", "device is offline")

	if received["text"] != "device is offline" {
		t.Fatalf("unexpected text field: %v", received["text"])
	}
	if received["username"] != "collector-status" {
		t.Fatalf("unexpected username field: %v", received["username"])
	}
	if received["icon_url"] != botIconURL {
		t.Fatalf("unexpected icon_url field: %v", received["icon_url"])
	}
	if _, ok := received["attachments"]; ok {
		t.Fatalf("did not expect attachments field for plain message")
	}
}

func TestSendMattermostMessageWithImageIncludesAttachment(t *testing.T) {
	var received map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("failed to read request body: %v", err)
		}
		if err := json.Unmarshal(body, &received); err != nil {
			t.Fatalf("failed to unmarshal payload: %v", err)
		}

		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	imageURL := "https://s3.example.com/chart.png"
	SendMattermostMessageWithImage(server.URL, "usage-notifier", "usage update", imageURL)

	attachments, ok := received["attachments"].([]any)
	if !ok {
		t.Fatalf("expected attachments array, got %T", received["attachments"])
	}
	if len(attachments) != 1 {
		t.Fatalf("expected one attachment, got %d", len(attachments))
	}

	firstAttachment, ok := attachments[0].(map[string]any)
	if !ok {
		t.Fatalf("expected first attachment to be object, got %T", attachments[0])
	}

	if firstAttachment["image_url"] != imageURL {
		t.Fatalf("expected image_url %q, got %v", imageURL, firstAttachment["image_url"])
	}
}

func TestSendMattermostMessageLogsOnNon200(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	var logBuffer strings.Builder
	originalOutput := log.Writer()
	log.SetOutput(&logBuffer)
	defer log.SetOutput(originalOutput)

	SendMattermostMessage(server.URL, "svc", "hello")

	if !strings.Contains(logBuffer.String(), "Mattermost webhook response:") {
		t.Fatalf("expected non-200 response to be logged, got: %s", logBuffer.String())
	}
}

func TestSendMattermostMessageInvalidWebhookFatal(t *testing.T) {
	if os.Getenv("TEST_INVALID_WEBHOOK_FATAL") == "1" {
		SendMattermostMessage("://bad-url", "svc", "hello")
		return
	}

	cmd := exec.Command(os.Args[0], "-test.run=TestSendMattermostMessageInvalidWebhookFatal")
	cmd.Env = append(os.Environ(), "TEST_INVALID_WEBHOOK_FATAL=1")

	err := cmd.Run()
	if err == nil {
		t.Fatal("expected process to exit with non-zero status")
	}

	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		t.Fatalf("expected *exec.ExitError, got %T (%v)", err, err)
	}
}
