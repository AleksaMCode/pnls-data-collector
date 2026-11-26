package firebase

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/internal/testsupport"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

const testNamespace = "demo-pnls"

// writeServiceAccount writes a service account file with a new key, like the one downloaded from the Firebase console.
func writeServiceAccount(t *testing.T, tokenURL string) string {
	t.Helper()

	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("failed to generate a key: %v", err)
	}
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})

	account, err := json.Marshal(map[string]string{
		"type":           "service_account",
		"project_id":     testNamespace,
		"private_key_id": "test-key",
		"private_key":    string(keyPEM),
		"client_email":   "notifier@demo-pnls.iam.gserviceaccount.com",
		"client_id":      "1",
		"token_uri":      tokenURL,
	})
	if err != nil {
		t.Fatalf("failed to encode the service account: %v", err)
	}

	path := filepath.Join(t.TempDir(), "firebase-credentials.json")
	if err := os.WriteFile(path, account, 0o600); err != nil {
		t.Fatalf("failed to write the service account: %v", err)
	}
	return path
}

// fakeRealtimeDatabase answers reads like the Realtime Database REST API, and records them.
type fakeRealtimeDatabase struct {
	server *httptest.Server
	mu     sync.Mutex
	reads  []*http.Request
}

func newFakeRealtimeDatabase(t *testing.T, nodes map[string]any) *fakeRealtimeDatabase {
	t.Helper()

	fake := &fakeRealtimeDatabase{}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/token" {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600}`))
			return
		}

		fake.mu.Lock()
		fake.reads = append(fake.reads, r)
		fake.mu.Unlock()

		node := strings.TrimSuffix(strings.TrimPrefix(r.URL.Path, "/"), ".json")
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(nodes[node])
	}))
	t.Cleanup(fake.server.Close)
	return fake
}

// databaseURL is the URL of the fake database in the emulator format, host:port?ns=<database name>.
func (f *fakeRealtimeDatabase) databaseURL() string {
	port := f.server.URL[strings.LastIndex(f.server.URL, ":")+1:]
	return "localhost:" + port + "?ns=" + testNamespace
}

func (f *fakeRealtimeDatabase) recordedReads() []*http.Request {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]*http.Request(nil), f.reads...)
}

func TestGetFirebaseClientReadsFromTheGivenDatabase(t *testing.T) {
	database := newFakeRealtimeDatabase(t, map[string]any{
		"RPI-1-2026-06-14": map[string]any{"status": map[string]any{"timestamp": "2026-06-14 12:00:00"}},
	})
	credentials := writeServiceAccount(t, database.server.URL+"/token")

	client := GetFirebaseClient(context.Background(), credentials, database.databaseURL())

	var node map[string]map[string]string
	if err := client.NewRef("RPI-1-2026-06-14").Get(context.Background(), &node); err != nil {
		t.Fatalf("failed to read the node: %v", err)
	}
	if got := node["status"]["timestamp"]; got != "2026-06-14 12:00:00" {
		t.Fatalf("unexpected node: %v", node)
	}

	reads := database.recordedReads()
	if len(reads) != 1 {
		t.Fatalf("expected one read, got %d", len(reads))
	}
	if reads[0].Method != http.MethodGet || reads[0].URL.Path != "/RPI-1-2026-06-14.json" {
		t.Fatalf("unexpected request: %s %s", reads[0].Method, reads[0].URL.Path)
	}
	if got := reads[0].URL.Query().Get("ns"); got != testNamespace {
		t.Fatalf("expected the namespace %q, got %q", testNamespace, got)
	}
}

func TestGetFirebaseClientMissingCredentialsFatal(t *testing.T) {
	if testsupport.InChild(t) {
		GetFirebaseClient(context.Background(), "definitely-missing-creds.json", "https://example.firebaseio.com")
		return
	}

	result := testsupport.RunInChild(t)

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
	if testsupport.InChild(t) {
		credentials := writeServiceAccount(t, "https://oauth2.googleapis.com/token")
		GetFirebaseClient(context.Background(), credentials, "not a database url")
		return
	}

	result := testsupport.RunInChild(t)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Error getting database client: not a database url: invalid database url") {
		t.Fatalf("expected the invalid URL to be logged, got:\n%s", result.Output())
	}
}

func TestGetFirebaseClientFailureIsReportedToSentry(t *testing.T) {
	if testsupport.InChild(t) {
		logging.InitSentry(os.Getenv(testsupport.SentryDSNEnv), "Collector status notifier")
		GetFirebaseClient(context.Background(), "definitely-missing-creds.json", "https://example.firebaseio.com")
		return
	}

	sentry := testsupport.NewFakeSentry(t)
	testsupport.RunInChild(t, testsupport.SentryDSNEnv+"="+sentry.DSN())

	testutil.ExpectFailure(t, "GetFirebaseClient exits with log.Fatalf, which skips Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) != 1 || events[0].Level != "fatal" {
			t.Fatalf("expected one fatal event in Sentry, got %+v", events)
		}
	})
}
