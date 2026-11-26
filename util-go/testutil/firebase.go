package testutil

import (
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
)

// FirebaseTestNamespace is the database name the fakes and the emulator use. A `demo-` project needs no Firebase login.
const FirebaseTestNamespace = "demo-pnls"

// WriteServiceAccount writes a service account file with a new key, like the one downloaded from the Firebase
// console, and returns its path. The SDK asks tokenURL for access tokens.
func WriteServiceAccount(t *testing.T, tokenURL string) string {
	t.Helper()

	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("failed to generate a key: %v", err)
	}
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})

	account, err := json.Marshal(map[string]string{
		"type":           "service_account",
		"project_id":     FirebaseTestNamespace,
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

// FakeRealtimeDatabase answers reads like the Realtime Database REST API, and records them. It also issues the
// access tokens, so a client made with its CredentialsFile works without a network.
type FakeRealtimeDatabase struct {
	server      *httptest.Server
	credentials string
	mu          sync.Mutex
	nodes       map[string]any
	requests    []*http.Request
	failStatus  int
	failNodes   map[string]bool
}

// NewFakeRealtimeDatabase starts a fake database with the given top-level nodes, closed when the test ends. A node
// that isn't in the map reads as null, as in Firebase.
func NewFakeRealtimeDatabase(t *testing.T, nodes map[string]any) *FakeRealtimeDatabase {
	t.Helper()

	fake := &FakeRealtimeDatabase{nodes: nodes}
	fake.server = httptest.NewServer(http.HandlerFunc(fake.serve))
	t.Cleanup(fake.server.Close)
	fake.credentials = WriteServiceAccount(t, fake.server.URL+"/token")
	return fake
}

func (f *FakeRealtimeDatabase) serve(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.URL.Path == "/token" {
		_, _ = w.Write([]byte(`{"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600}`))
		return
	}

	node := strings.TrimSuffix(strings.TrimPrefix(r.URL.Path, "/"), ".json")

	f.mu.Lock()
	defer f.mu.Unlock()
	f.requests = append(f.requests, r.Clone(r.Context()))
	if f.failStatus != 0 && (len(f.failNodes) == 0 || f.failNodes[node]) {
		w.WriteHeader(f.failStatus)
		_, _ = w.Write([]byte(`{"error": "test failure"}`))
		return
	}
	_ = json.NewEncoder(w).Encode(f.nodes[node])
}

// DatabaseURL is the URL of the fake database in the emulator format, host:port?ns=<database name>.
func (f *FakeRealtimeDatabase) DatabaseURL() string {
	port := f.server.URL[strings.LastIndex(f.server.URL, ":")+1:]
	return "localhost:" + port + "?ns=" + FirebaseTestNamespace
}

// CredentialsFile is a service account whose tokens come from the fake database.
func (f *FakeRealtimeDatabase) CredentialsFile() string {
	return f.credentials
}

// FailReads makes reads of the given nodes, or of every node when none is given, answer with the status.
func (f *FakeRealtimeDatabase) FailReads(status int, nodes ...string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.failStatus = status
	f.failNodes = map[string]bool{}
	for _, node := range nodes {
		f.failNodes[node] = true
	}
}

// Requests returns the database requests received so far, without the token requests.
func (f *FakeRealtimeDatabase) Requests() []*http.Request {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]*http.Request(nil), f.requests...)
}

// Reads returns the paths read so far, without the leading slash and the .json suffix.
func (f *FakeRealtimeDatabase) Reads() []string {
	requests := f.Requests()
	reads := make([]string, 0, len(requests))
	for _, request := range requests {
		reads = append(reads, strings.TrimSuffix(strings.TrimPrefix(request.URL.Path, "/"), ".json"))
	}
	return reads
}
