package testsupport

import (
	"bufio"
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

// SentryDSNEnv passes the DSN of a FakeSentry to a child process started by RunInChild.
const SentryDSNEnv = "UTIL_GO_TEST_SENTRY_DSN"

// SentryEvent is the part of a Sentry event the tests look at.
type SentryEvent struct {
	Message    string `json:"message"`
	Level      string `json:"level"`
	ServerName string `json:"server_name"`
}

// FakeSentry is a local server that accepts the envelopes the Sentry SDK sends and keeps their events.
type FakeSentry struct {
	server *httptest.Server
	mu     sync.Mutex
	events []SentryEvent
}

// NewFakeSentry starts a fake Sentry server, which is closed when the test ends.
func NewFakeSentry(t *testing.T) *FakeSentry {
	t.Helper()

	fake := &FakeSentry{}
	fake.server = httptest.NewServer(http.HandlerFunc(fake.receive))
	t.Cleanup(fake.server.Close)
	return fake
}

// DSN points the Sentry SDK at the fake server.
func (f *FakeSentry) DSN() string {
	return "http://public@" + strings.TrimPrefix(f.server.URL, "http://") + "/1"
}

// Events returns the events received so far.
func (f *FakeSentry) Events() []SentryEvent {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]SentryEvent(nil), f.events...)
}

// WaitForEvents waits until at least n events arrived, or the timeout passed, and returns the events received.
func (f *FakeSentry) WaitForEvents(n int, timeout time.Duration) []SentryEvent {
	deadline := time.Now().Add(timeout)
	for {
		events := f.Events()
		if len(events) >= n || time.Now().After(deadline) {
			return events
		}
		time.Sleep(10 * time.Millisecond)
	}
}

// receive reads an envelope: a header line, then a header line and a payload line per item.
func (f *FakeSentry) receive(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	scanner := bufio.NewScanner(bytes.NewReader(body))
	scanner.Buffer(make([]byte, 0, 64*1024), 10*1024*1024)
	scanner.Scan() // envelope header
	for scanner.Scan() {
		var item struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(scanner.Bytes(), &item); err != nil || !scanner.Scan() {
			break
		}
		if item.Type != "event" {
			continue
		}
		var event SentryEvent
		if err := json.Unmarshal(scanner.Bytes(), &event); err == nil {
			f.mu.Lock()
			f.events = append(f.events, event)
			f.mu.Unlock()
		}
	}
	w.WriteHeader(http.StatusOK)
}
