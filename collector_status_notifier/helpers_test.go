package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"firebase.google.com/go/v4/db"
	"github.com/alicebob/miniredis/v2"

	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// configNames are the environment variables the service reads.
var configNames = []string{
	"MATTERMOST_WEBHOOK_URL", "FIREBASE_DATABASE_URL", "SENTRY_DSN", "DATADOG_API_KEY", "DATADOG_APP_KEY",
	"DATADOG_HEARTBEAT_METRIC", "DATADOG_HOST", "REDIS_URL", "REDIS_PORT", "REDIS_PASSWORD", "REDIS_DB",
	"KUMA_PUSH_ENABLED", "KUMA_PUSH_URL",
}

// configVariables are the string configuration variables, by the name of their environment variable.
func configVariables() map[string]*string {
	return map[string]*string{
		"MATTERMOST_WEBHOOK_URL":   &MATTERMOST_WEBHOOK_URL,
		"FIREBASE_DATABASE_URL":    &FIREBASE_DATABASE_URL,
		"SENTRY_DSN":               &SENTRY_DSN,
		"DATADOG_API_KEY":          &DATADOG_API_KEY,
		"DATADOG_APP_KEY":          &DATADOG_APP_KEY,
		"DATADOG_HEARTBEAT_METRIC": &DATADOG_HEARTBEAT_METRIC,
		"DATADOG_HOST":             &DATADOG_HOST,
		"REDIS_URL":                &REDIS_URL,
		"REDIS_PORT":               &REDIS_PORT,
		"REDIS_PASSWORD":           &REDIS_PASSWORD,
		"REDIS_DB":                 &REDIS_DB,
		"KUMA_PUSH_URL":            &KUMA_PUSH_URL,
	}
}

// restoreConfig puts the configuration variables back when the test ends.
func restoreConfig(t *testing.T) {
	t.Helper()

	saved := map[string]string{}
	for name, variable := range configVariables() {
		saved[name] = *variable
	}
	kumaEnabled := KUMA_PUSH_ENABLED
	t.Cleanup(func() {
		for name, variable := range configVariables() {
			*variable = saved[name]
		}
		KUMA_PUSH_ENABLED = kumaEnabled
	})
}

// unsetConfigEnv removes the configuration from the environment until the test ends, as godotenv doesn't replace
// variables that are already set.
func unsetConfigEnv(t *testing.T) {
	t.Helper()

	for _, name := range configNames {
		t.Setenv(name, "")
		if err := os.Unsetenv(name); err != nil {
			t.Fatalf("failed to unset %s: %v", name, err)
		}
	}
}

// writeEnvFile writes a .env file with the values into a new folder and returns the folder.
func writeEnvFile(t *testing.T, values map[string]string) string {
	t.Helper()

	var content strings.Builder
	for _, name := range configNames {
		if value, ok := values[name]; ok {
			fmt.Fprintf(&content, "%s=%s\n", name, value)
		}
	}
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, ".env"), []byte(content.String()), 0o600); err != nil {
		t.Fatalf("failed to write the .env file: %v", err)
	}
	return dir
}

// useMiniredis connects the service to a new in-memory Redis until the test ends.
func useMiniredis(t *testing.T) *miniredis.Miniredis {
	t.Helper()

	server := miniredis.RunT(t)
	restoreConfig(t)
	REDIS_URL, REDIS_PORT, REDIS_PASSWORD, REDIS_DB = server.Host(), server.Port(), "", "0"
	if err := initRedisClient(context.Background()); err != nil {
		t.Fatalf("failed to connect to miniredis: %v", err)
	}
	t.Cleanup(func() {
		_ = closeRedisClient()
		redisClient = nil
	})
	return server
}

// useWebhook sends the Mattermost messages to a fake webhook until the test ends.
func useWebhook(t *testing.T) *testutil.FakeWebhook {
	t.Helper()

	webhook := testutil.NewFakeWebhook(t)
	restoreConfig(t)
	MATTERMOST_WEBHOOK_URL = webhook.URL()
	return webhook
}

// texts are the texts of the messages the webhook received.
func texts(webhook *testutil.FakeWebhook) []string {
	var texts []string
	for _, message := range webhook.Messages() {
		text, _ := message["text"].(string)
		texts = append(texts, text)
	}
	return texts
}

// cachedOffline returns the offline state Redis holds for the device, or nil.
func cachedOffline(t *testing.T, device string) *offlineDeviceCache {
	t.Helper()

	cached, err := getOfflineDeviceCache(context.Background(), device)
	if err != nil {
		t.Fatalf("failed to read the cache of %s: %v", device, err)
	}
	return cached
}

// datadogQuery is a query the fake Datadog API received.
type datadogQuery struct {
	apiKey, appKey, query string
	from, to              int64
}

// fakeDatadog answers metric queries like Datadog's v1 query API. Each device answers its heartbeat points, or its
// status and body when one is set.
type fakeDatadog struct {
	server  *httptest.Server
	mu      sync.Mutex
	points  map[string][]time.Time
	failing map[string]fakeReply
	queries []datadogQuery
}

type fakeReply struct {
	status int
	body   string
}

func newFakeDatadog(t *testing.T) *fakeDatadog {
	t.Helper()

	fake := &fakeDatadog{points: map[string][]time.Time{}, failing: map[string]fakeReply{}}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/query" {
			t.Errorf("unexpected Datadog path %s", r.URL.Path)
		}
		query := r.URL.Query()
		from, _ := strconv.ParseInt(query.Get("from"), 10, 64)
		to, _ := strconv.ParseInt(query.Get("to"), 10, 64)
		device := strings.TrimSuffix(strings.TrimPrefix(query.Get("query"), "avg:pnls.heartbeat{host:"), "}")

		fake.mu.Lock()
		fake.queries = append(fake.queries, datadogQuery{
			apiKey: r.Header.Get("DD-API-KEY"), appKey: r.Header.Get("DD-APPLICATION-KEY"),
			query: query.Get("query"), from: from, to: to,
		})
		reply, failing := fake.failing[device]
		points := fake.points[device]
		fake.mu.Unlock()

		if failing {
			w.WriteHeader(reply.status)
			_, _ = w.Write([]byte(reply.body))
			return
		}
		pointlist := make([][]*float64, 0, len(points))
		for _, at := range points {
			millis, value := float64(at.UnixMilli()), 1.0
			pointlist = append(pointlist, []*float64{&millis, &value})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status": "ok",
			"series": []map[string]any{{"pointlist": pointlist}},
		})
	}))
	t.Cleanup(fake.server.Close)
	return fake
}

// heartbeat sets the times of the device's heartbeat points.
func (f *fakeDatadog) heartbeat(device string, at ...time.Time) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.points[device] = at
}

// fail makes the queries of the device answer with the status and body.
func (f *fakeDatadog) fail(device string, status int, body string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.failing[device] = fakeReply{status: status, body: body}
}

func (f *fakeDatadog) received() []datadogQuery {
	f.mu.Lock()
	defer f.mu.Unlock()
	return slices.Clone(f.queries)
}

// useFakeDatadog points the Datadog check at a fake API until the test ends.
func useFakeDatadog(t *testing.T) *fakeDatadog {
	t.Helper()

	fake := newFakeDatadog(t)
	restoreConfig(t)
	DATADOG_API_KEY, DATADOG_APP_KEY = "api-key", "app-key"
	DATADOG_HEARTBEAT_METRIC, DATADOG_HOST = "pnls.heartbeat", fake.server.URL
	return fake
}

// parisNow is the current time in Paris, the zone the collectors write their heartbeats in.
func parisNow(t *testing.T) time.Time {
	t.Helper()

	paris, err := time.LoadLocation(TIMEZONE)
	if err != nil {
		t.Fatalf("failed to load %s: %v", TIMEZONE, err)
	}
	return time.Now().In(paris)
}

// statusNode is the Firebase path of a device's status on the day of the time, e.g. RPI-1-2026-11-27/status.
func statusNode(device string, day time.Time) string {
	return fmt.Sprintf("%s-%s/status", device, day.Format("2006-01-02"))
}

// status is a device status as the collector writes it, with its heartbeat at the time.
func status(at time.Time) map[string]any {
	return map[string]any{"status": "working", "timestamp": at.Format(TIMESTAMP_FORMAT)}
}

// newFakeFirebase starts a fake database with the nodes, and returns it with a client for it.
func newFakeFirebase(t *testing.T, nodes map[string]any) (*testutil.FakeRealtimeDatabase, *db.Client) {
	t.Helper()

	fake := testutil.NewFakeRealtimeDatabase(t, nodes)
	return fake, firebase.GetFirebaseClient(context.Background(), fake.CredentialsFile(), fake.DatabaseURL())
}

// fakeKuma is an Uptime Kuma push monitor that counts the pushes, and tells the count at /pushes, so a child process
// can wait for its push to arrive.
type fakeKuma struct {
	server *httptest.Server
	mu     sync.Mutex
	pushes int
}

// useFakeKuma turns the Uptime Kuma push on, to a fake monitor, until the test ends.
func useFakeKuma(t *testing.T) *fakeKuma {
	t.Helper()

	fake := &fakeKuma{}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fake.mu.Lock()
		defer fake.mu.Unlock()
		if r.URL.Path == "/pushes" {
			_, _ = fmt.Fprint(w, fake.pushes)
			return
		}
		fake.pushes++
	}))
	t.Cleanup(fake.server.Close)
	restoreConfig(t)
	KUMA_PUSH_ENABLED, KUMA_PUSH_URL = true, fake.server.URL+"/api/push/token?status=up"
	return fake
}

func (f *fakeKuma) count() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.pushes
}

// pushesURL is where the fake tells how many pushes it received.
func (f *fakeKuma) pushesURL() string {
	return f.server.URL + "/pushes"
}

// kumaPushes asks a fake Kuma at pushesURL how many pushes it received, or returns -1 when it can't be asked.
func kumaPushes(pushesURL string) int {
	response, err := http.Get(pushesURL) //nolint:gosec,noctx // G107: the URL is the test's fake Kuma.
	if err != nil {
		return -1
	}
	defer response.Body.Close()
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return -1
	}
	count, err := strconv.Atoi(string(body))
	if err != nil {
		return -1
	}
	return count
}
