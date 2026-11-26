package firebase

import (
	"context"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func TestGetFirebaseClientReadsFromTheGivenDatabase(t *testing.T) {
	database := testutil.NewFakeRealtimeDatabase(t, map[string]any{
		"RPI-1-2026-06-14": map[string]any{"status": map[string]any{"timestamp": "2026-06-14 12:00:00"}},
	})

	client := GetFirebaseClient(context.Background(), database.CredentialsFile(), database.DatabaseURL())

	var node map[string]map[string]string
	if err := client.NewRef("RPI-1-2026-06-14").Get(context.Background(), &node); err != nil {
		t.Fatalf("failed to read the node: %v", err)
	}
	if got := node["status"]["timestamp"]; got != "2026-06-14 12:00:00" {
		t.Fatalf("unexpected node: %v", node)
	}

	requests := database.Requests()
	if len(requests) != 1 {
		t.Fatalf("expected one read, got %d", len(requests))
	}
	if requests[0].Method != http.MethodGet || requests[0].URL.Path != "/RPI-1-2026-06-14.json" {
		t.Fatalf("unexpected request: %s %s", requests[0].Method, requests[0].URL.Path)
	}
	if got := requests[0].URL.Query().Get("ns"); got != testutil.FirebaseTestNamespace {
		t.Fatalf("expected the namespace %q, got %q", testutil.FirebaseTestNamespace, got)
	}
}

func TestGetFirebaseClientMissingCredentialsFatal(t *testing.T) {
	if testutil.InChild(t) {
		GetFirebaseClient(context.Background(), "definitely-missing-creds.json", "https://example.firebaseio.com")
		return
	}

	result := testutil.RunInChild(t)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	// The app is created without reading the file; the database client is the first to read it.
	want := "Error getting database client: cannot read credentials file"
	if !strings.Contains(result.Output(), want) {
		t.Fatalf("expected %q in the output, got:\n%s", want, result.Output())
	}
}

func TestGetFirebaseClientInvalidDatabaseURLFatal(t *testing.T) {
	if testutil.InChild(t) {
		credentials := testutil.WriteServiceAccount(t, "https://oauth2.googleapis.com/token")
		GetFirebaseClient(context.Background(), credentials, "not a database url")
		return
	}

	result := testutil.RunInChild(t)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Error getting database client: not a database url: invalid database url") {
		t.Fatalf("expected the invalid URL to be logged, got:\n%s", result.Output())
	}
}

func TestGetFirebaseClientFailureIsReportedToSentry(t *testing.T) {
	if testutil.InChild(t) {
		logging.InitSentry(os.Getenv(testutil.SentryDSNEnv), "Collector status notifier")
		GetFirebaseClient(context.Background(), "definitely-missing-creds.json", "https://example.firebaseio.com")
		return
	}

	sentry := testutil.NewFakeSentry(t)
	testutil.RunInChild(t, testutil.SentryDSNEnv+"="+sentry.DSN())

	testutil.ExpectFailure(t, "GetFirebaseClient exits with log.Fatalf, which skips Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) != 1 || events[0].Level != "fatal" {
			t.Fatalf("expected one fatal event in Sentry, got %+v", events)
		}
	})
}
