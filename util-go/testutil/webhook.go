package testutil

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

// FakeWebhook is a Mattermost incoming webhook that records the messages it receives.
type FakeWebhook struct {
	server   *httptest.Server
	mu       sync.Mutex
	messages []map[string]any
	headers  []http.Header
	status   int
	reply    string
}

// NewFakeWebhook starts a webhook that answers 200 "ok", and is closed when the test ends.
func NewFakeWebhook(t *testing.T) *FakeWebhook {
	t.Helper()

	fake := &FakeWebhook{status: http.StatusOK, reply: "ok"}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Errorf("failed to read the request body: %v", err)
		}
		var message map[string]any
		if err := json.Unmarshal(body, &message); err != nil {
			t.Errorf("expected a JSON body, got %q: %v", body, err)
		}
		if r.Method != http.MethodPost {
			t.Errorf("expected a POST request, got %s", r.Method)
		}

		fake.mu.Lock()
		defer fake.mu.Unlock()
		fake.messages = append(fake.messages, message)
		fake.headers = append(fake.headers, r.Header.Clone())
		w.WriteHeader(fake.status)
		_, _ = w.Write([]byte(fake.reply))
	}))
	t.Cleanup(fake.server.Close)
	return fake
}

// URL is the webhook URL to configure.
func (f *FakeWebhook) URL() string {
	return f.server.URL
}

// Answer sets the status and body of the next replies.
func (f *FakeWebhook) Answer(status int, reply string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.status = status
	f.reply = reply
}

// Messages returns the messages received so far.
func (f *FakeWebhook) Messages() []map[string]any {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]map[string]any(nil), f.messages...)
}

// Headers returns the headers of the requests received so far.
func (f *FakeWebhook) Headers() []http.Header {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]http.Header(nil), f.headers...)
}

// OnlyMessage returns the one message the webhook received, and fails the test if it got another number.
func (f *FakeWebhook) OnlyMessage(t TB) map[string]any {
	t.Helper()

	messages := f.Messages()
	if len(messages) != 1 {
		t.Fatalf("expected one message, got %d: %v", len(messages), messages)
	}
	return messages[0]
}

// RefusedURL is the URL of a server that was closed, so connections to it are refused.
func RefusedURL() string {
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	server.Close()
	return server.URL
}

// CaptureLog sends the standard logger to a buffer until the test ends.
func CaptureLog(t *testing.T) *strings.Builder {
	t.Helper()

	var buffer strings.Builder
	original := log.Writer()
	log.SetOutput(&buffer)
	t.Cleanup(func() { log.SetOutput(original) })
	return &buffer
}
