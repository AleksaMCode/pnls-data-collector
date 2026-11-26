package mattermost

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

const iconBaseURL = "https://raw.githubusercontent.com/AleksaMCode/pnls-data-collector/master/resources/bot_icons/"

// fakeWebhook is a Mattermost incoming webhook that records the messages it receives.
type fakeWebhook struct {
	server   *httptest.Server
	mu       sync.Mutex
	messages []map[string]any
	headers  []http.Header
	status   int
	reply    string
}

func newFakeWebhook(t *testing.T) *fakeWebhook {
	t.Helper()

	fake := &fakeWebhook{status: http.StatusOK, reply: "ok"}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Errorf("failed to read the request body: %v", err)
		}
		var message map[string]any
		if err := json.Unmarshal(body, &message); err != nil {
			t.Errorf("expected a JSON body, got %q: %v", body, err)
		}

		fake.mu.Lock()
		defer fake.mu.Unlock()
		if r.Method != http.MethodPost {
			t.Errorf("expected a POST request, got %s", r.Method)
		}
		fake.messages = append(fake.messages, message)
		fake.headers = append(fake.headers, r.Header.Clone())
		w.WriteHeader(fake.status)
		_, _ = w.Write([]byte(fake.reply))
	}))
	t.Cleanup(fake.server.Close)
	return fake
}

func (f *fakeWebhook) answer(status int, reply string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.status = status
	f.reply = reply
}

// onlyMessage returns the one message the webhook received.
func (f *fakeWebhook) onlyMessage(t *testing.T) map[string]any {
	t.Helper()

	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.messages) != 1 {
		t.Fatalf("expected one message, got %d: %v", len(f.messages), f.messages)
	}
	return f.messages[0]
}

// refusedURL is the URL of a server that was closed, so connections to it are refused.
func refusedURL() string {
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	server.Close()
	return server.URL
}

func captureLog(t *testing.T) *strings.Builder {
	t.Helper()

	var buffer strings.Builder
	original := log.Writer()
	log.SetOutput(&buffer)
	t.Cleanup(func() { log.SetOutput(original) })
	return &buffer
}

func TestSendMattermostMessagePostsExpectedPayload(t *testing.T) {
	webhook := newFakeWebhook(t)

	SendMattermostMessage(webhook.server.URL, "Collector status notifier", "RPI-1 is offline.")

	message := webhook.onlyMessage(t)
	want := map[string]any{
		"text":     "RPI-1 is offline.",
		"username": "Collector status notifier",
		"icon_url": iconBaseURL + "status_notifier.png",
	}
	if len(message) != len(want) {
		t.Fatalf("expected the fields %v, got %v", want, message)
	}
	for field, value := range want {
		if message[field] != value {
			t.Errorf("expected %s %q, got %v", field, value, message[field])
		}
	}
	if got := webhook.headers[0].Get("Content-Type"); got != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", got)
	}
}

func TestEachServiceHasItsOwnIcon(t *testing.T) {
	for serviceName, icon := range map[string]string{
		"Cloudflare limit notifier":  "limit_notifier.png",
		"Firebase limit notifier":    "limit_notifier.png",
		"Home Server limit notifier": "limit_notifier.png",
		"Collector status notifier":  "status_notifier.png",
		"Unknown service":            "status_notifier.png",
	} {
		t.Run(serviceName, func(t *testing.T) {
			webhook := newFakeWebhook(t)

			if err := TrySendMattermostMessage(webhook.server.URL, serviceName, "hello"); err != nil {
				t.Fatalf("expected no error, got %v", err)
			}

			message := webhook.onlyMessage(t)
			if message["username"] != serviceName || message["icon_url"] != iconBaseURL+icon {
				t.Fatalf("expected %q with the icon %s, got %v", serviceName, icon, message)
			}
		})
	}
}

func TestMultiLineAndNonASCIITextIsSentAsIs(t *testing.T) {
	webhook := newFakeWebhook(t)
	text := "### Firebase usage\n| Device | Usage |\n|---|---|\n| RPI-1 | 42 % ✓ |"

	SendMattermostMessage(webhook.server.URL, "Firebase limit notifier", text)

	if got := webhook.onlyMessage(t)["text"]; got != text {
		t.Fatalf("expected %q, got %q", text, got)
	}
}

func TestSendMattermostMessageWithImageIncludesAttachment(t *testing.T) {
	webhook := newFakeWebhook(t)
	imageURL := "https://charts.example.com/firebase-usage-2026-06-14.png"

	SendMattermostMessageWithImage(webhook.server.URL, "Firebase limit notifier", "Usage update.", imageURL)

	attachments, ok := webhook.onlyMessage(t)["attachments"].([]any)
	if !ok || len(attachments) != 1 {
		t.Fatalf("expected one attachment, got %v", webhook.onlyMessage(t)["attachments"])
	}
	want := map[string]any{
		"title":     "Cloudflare R2 bucket hosted chart",
		"text":      "Pie chart Firebase Realtime DB usage",
		"color":     "#FF5733",
		"image_url": imageURL,
	}
	attachment, _ := attachments[0].(map[string]any)
	if len(attachment) != len(want) {
		t.Fatalf("expected the fields %v, got %v", want, attachment)
	}
	for field, value := range want {
		if attachment[field] != value {
			t.Errorf("expected %s %q, got %v", field, value, attachment[field])
		}
	}
}

func TestMessageWithoutImageURLHasNoAttachment(t *testing.T) {
	webhook := newFakeWebhook(t)

	if err := TrySendMattermostMessageWithImage(webhook.server.URL, "svc", "hello", ""); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if attachments, ok := webhook.onlyMessage(t)["attachments"]; ok {
		t.Fatalf("did not expect attachments, got %v", attachments)
	}
}

func TestSuccessIsLogged(t *testing.T) {
	webhook := newFakeWebhook(t)
	logs := captureLog(t)

	SendMattermostMessage(webhook.server.URL, "svc", "hello")

	if !strings.Contains(logs.String(), "Successfully sent message to Mattermost!") {
		t.Fatalf("expected the success to be logged, got:\n%s", logs.String())
	}
}

func TestSendMattermostMessageLogsOnNon200(t *testing.T) {
	webhook := newFakeWebhook(t)
	webhook.answer(http.StatusInternalServerError, "")
	logs := captureLog(t)

	SendMattermostMessage(webhook.server.URL, "svc", "hello")

	if !strings.Contains(logs.String(), "Mattermost webhook response: 500 Internal Server Error") {
		t.Fatalf("expected the status to be logged, got:\n%s", logs.String())
	}
	if strings.Contains(logs.String(), "Successfully") {
		t.Fatalf("did not expect a success to be logged, got:\n%s", logs.String())
	}
}

func TestSendMattermostMessageInvalidWebhookFatal(t *testing.T) {
	if testutil.InChild(t) {
		SendMattermostMessage("://bad-url", "svc", "hello")
		return
	}

	result := testutil.RunInChild(t)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "failed to create HTTP request") {
		t.Fatalf("expected the error to be logged, got:\n%s", result.Output())
	}
}

func TestSendMattermostMessageUnreachableWebhookFatal(t *testing.T) {
	if testutil.InChild(t) {
		SendMattermostMessageWithImage(os.Getenv("UTIL_GO_TEST_WEBHOOK"), "svc", "hello", "https://example.com/a.png")
		return
	}

	result := testutil.RunInChild(t, "UTIL_GO_TEST_WEBHOOK="+refusedURL())

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "failed to send message to Mattermost") {
		t.Fatalf("expected the error to be logged, got:\n%s", result.Output())
	}
}

func TestTrySendMattermostMessageReturnsNilOnSuccess(t *testing.T) {
	webhook := newFakeWebhook(t)

	if err := TrySendMattermostMessage(webhook.server.URL, "svc", "hello"); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	err := TrySendMattermostMessageWithImage(webhook.server.URL, "svc", "hello", "https://example.com/a.png")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestTrySendMattermostMessageReturnsErrorOnNon200(t *testing.T) {
	webhook := newFakeWebhook(t)
	webhook.answer(http.StatusInternalServerError, "")

	err := TrySendMattermostMessage(webhook.server.URL, "svc", "hello")

	if err == nil || err.Error() != "Mattermost webhook response: 500 Internal Server Error" {
		t.Fatalf("expected the status in the error, got %v", err)
	}
}

func TestTrySendMattermostMessageReturnsErrorOnInvalidWebhook(t *testing.T) {
	err := TrySendMattermostMessage("://bad-url", "svc", "hello")

	if err == nil || !strings.Contains(err.Error(), "failed to create HTTP request") {
		t.Fatalf("expected an error for an invalid webhook URL, got %v", err)
	}
}

func TestTrySendMattermostMessageReturnsErrorWhenConnectionIsRefused(t *testing.T) {
	err := TrySendMattermostMessageWithImage(refusedURL(), "svc", "hello", "")

	if err == nil || !strings.Contains(err.Error(), "failed to send message to Mattermost") {
		t.Fatalf("expected an error for a refused connection, got %v", err)
	}
}

func TestErrorIncludesWhatMattermostReplied(t *testing.T) {
	webhook := newFakeWebhook(t)
	webhook.answer(http.StatusBadRequest, "Unable to parse incoming data")

	err := TrySendMattermostMessage(webhook.server.URL, "svc", "hello")

	testutil.ExpectFailure(t, "only the status is kept, the reply body is dropped.", func(t testutil.TB) {
		if err == nil || !strings.Contains(err.Error(), "Unable to parse incoming data") {
			t.Fatalf("expected the reply in the error, got %v", err)
		}
	})
}

func TestRequestTimesOut(t *testing.T) {
	if testing.Short() {
		t.Skip("waits 11 seconds")
	}

	// Mattermost accepts the connection but never answers.
	release := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { <-release }))
	t.Cleanup(server.Close)
	t.Cleanup(func() { close(release) })

	result := make(chan error, 1)
	go func() { result <- TrySendMattermostMessage(server.URL, "svc", "hello") }()

	testutil.ExpectFailure(t, "http.DefaultClient has no timeout, so the call blocks forever.", func(t testutil.TB) {
		select {
		case err := <-result:
			if err == nil {
				t.Fatal("expected an error for a webhook that never answers")
			}
		case <-time.After(11 * time.Second):
			t.Fatal("the request was still waiting after 11 seconds")
		}
	})
}

func TestDeliveryFailureIsReportedToSentry(t *testing.T) {
	if testutil.InChild(t) {
		logging.InitSentry(os.Getenv(testutil.SentryDSNEnv), "Collector status notifier")
		SendMattermostMessage(os.Getenv("UTIL_GO_TEST_WEBHOOK"), "Collector status notifier", "RPI-1 is offline.")
		return
	}

	sentry := testutil.NewFakeSentry(t)
	testutil.RunInChild(t, testutil.SentryDSNEnv+"="+sentry.DSN(), "UTIL_GO_TEST_WEBHOOK="+refusedURL())

	testutil.ExpectFailure(t, "a failed delivery exits with log.Fatal, which skips Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) != 1 || events[0].Level != "fatal" {
			t.Fatalf("expected one fatal event in Sentry, got %+v", events)
		}
	})
}
