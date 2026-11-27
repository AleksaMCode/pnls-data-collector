package mattermost

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

const iconBaseURL = "https://raw.githubusercontent.com/AleksaMCode/pnls-data-collector/master/resources/bot_icons/"

func TestSendMattermostMessagePostsExpectedPayload(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)

	SendMattermostMessage(webhook.URL(), "Collector status notifier", "RPI-1 is offline.")

	message := webhook.OnlyMessage(t)
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
	if got := webhook.Headers()[0].Get("Content-Type"); got != "application/json" {
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
			webhook := testutil.NewFakeWebhook(t)

			if err := TrySendMattermostMessage(webhook.URL(), serviceName, "hello"); err != nil {
				t.Fatalf("expected no error, got %v", err)
			}

			message := webhook.OnlyMessage(t)
			if message["username"] != serviceName || message["icon_url"] != iconBaseURL+icon {
				t.Fatalf("expected %q with the icon %s, got %v", serviceName, icon, message)
			}
		})
	}
}

func TestMultiLineAndNonASCIITextIsSentAsIs(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	text := "### Firebase usage\n| Device | Usage |\n|---|---|\n| RPI-1 | 42 % ✓ |"

	SendMattermostMessage(webhook.URL(), "Firebase limit notifier", text)

	if got := webhook.OnlyMessage(t)["text"]; got != text {
		t.Fatalf("expected %q, got %q", text, got)
	}
}

func TestSendMattermostMessageWithImageIncludesAttachment(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	imageURL := "https://charts.example.com/firebase-usage-2026-06-14.png"

	SendMattermostMessageWithImage(webhook.URL(), "Firebase limit notifier", "Usage update.", imageURL)

	attachments, ok := webhook.OnlyMessage(t)["attachments"].([]any)
	if !ok || len(attachments) != 1 {
		t.Fatalf("expected one attachment, got %v", webhook.OnlyMessage(t)["attachments"])
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
	webhook := testutil.NewFakeWebhook(t)

	if err := TrySendMattermostMessageWithImage(webhook.URL(), "svc", "hello", ""); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if attachments, ok := webhook.OnlyMessage(t)["attachments"]; ok {
		t.Fatalf("did not expect attachments, got %v", attachments)
	}
}

func TestSuccessIsLogged(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	logs := testutil.CaptureLog(t)

	SendMattermostMessage(webhook.URL(), "svc", "hello")

	if !strings.Contains(logs.String(), "Successfully sent message to Mattermost!") {
		t.Fatalf("expected the success to be logged, got:\n%s", logs.String())
	}
}

func TestSendMattermostMessageLogsOnNon200(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	webhook.Answer(http.StatusInternalServerError, "")
	logs := testutil.CaptureLog(t)

	SendMattermostMessage(webhook.URL(), "svc", "hello")

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

	result := testutil.RunInChild(t, "UTIL_GO_TEST_WEBHOOK="+testutil.RefusedURL())

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "failed to send message to Mattermost") {
		t.Fatalf("expected the error to be logged, got:\n%s", result.Output())
	}
}

func TestTrySendMattermostMessageReturnsNilOnSuccess(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)

	if err := TrySendMattermostMessage(webhook.URL(), "svc", "hello"); err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	err := TrySendMattermostMessageWithImage(webhook.URL(), "svc", "hello", "https://example.com/a.png")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestTrySendMattermostMessageReturnsErrorOnNon200(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	webhook.Answer(http.StatusInternalServerError, "")

	err := TrySendMattermostMessage(webhook.URL(), "svc", "hello")

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
	err := TrySendMattermostMessageWithImage(testutil.RefusedURL(), "svc", "hello", "")

	if err == nil || !strings.Contains(err.Error(), "failed to send message to Mattermost") {
		t.Fatalf("expected an error for a refused connection, got %v", err)
	}
}

func TestErrorIncludesWhatMattermostReplied(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	webhook.Answer(http.StatusBadRequest, "Unable to parse incoming data")

	err := TrySendMattermostMessage(webhook.URL(), "svc", "hello")

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
	testutil.RunInChild(t, testutil.SentryDSNEnv+"="+sentry.DSN(), "UTIL_GO_TEST_WEBHOOK="+testutil.RefusedURL())

	testutil.ExpectFailure(t, "a failed delivery exits with log.Fatal, which skips Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) != 1 || events[0].Level != "fatal" {
			t.Fatalf("expected one fatal event in Sentry, got %+v", events)
		}
	})
}
