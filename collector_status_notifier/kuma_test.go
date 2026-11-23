package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestValidateKumaConfig(t *testing.T) {
	tests := []struct {
		name      string
		enabled   bool
		pushURL   string
		expectErr bool
	}{
		{name: "disabled without url", enabled: false, pushURL: "", expectErr: false},
		{name: "disabled with invalid url", enabled: false, pushURL: "not a url", expectErr: false},
		{
			name:      "enabled with http url",
			enabled:   true,
			pushURL:   "http://uptime_kuma:3001/api/push/abc",
			expectErr: false,
		},
		{
			name:      "enabled with https url",
			enabled:   true,
			pushURL:   "https://kuma.example.com/api/push/abc",
			expectErr: false,
		},
		{name: "enabled without url", enabled: true, pushURL: "", expectErr: true},
		{name: "enabled without scheme", enabled: true, pushURL: "uptime_kuma:3001/api/push/abc", expectErr: true},
		{
			name:      "enabled with unsupported scheme",
			enabled:   true,
			pushURL:   "ftp://uptime_kuma/api/push/abc",
			expectErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateKumaConfig(tt.enabled, tt.pushURL)
			if (err != nil) != tt.expectErr {
				t.Errorf("validateKumaConfig() error = %v, expectErr %v", err, tt.expectErr)
			}
		})
	}
}

func TestParseBoolEnv(t *testing.T) {
	tests := []struct {
		name      string
		value     string
		expected  bool
		expectErr bool
	}{
		{name: "unset falls back to false", value: "", expected: false},
		{name: "true", value: "true", expected: true},
		{name: "uppercase true", value: "TRUE", expected: true},
		{name: "one", value: "1", expected: true},
		{name: "false", value: "false", expected: false},
		{name: "surrounding spaces", value: " true ", expected: true},
		{name: "invalid", value: "yes please", expectErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("KUMA_TEST_FLAG", tt.value)

			result, err := parseBoolEnv("KUMA_TEST_FLAG")
			if (err != nil) != tt.expectErr {
				t.Fatalf("parseBoolEnv() error = %v, expectErr %v", err, tt.expectErr)
			}
			if result != tt.expected {
				t.Errorf("parseBoolEnv() = %v, want %v", result, tt.expected)
			}
		})
	}
}

func TestPushKumaHeartbeat(t *testing.T) {
	tests := []struct {
		name       string
		statusCode int
		expectErr  bool
	}{
		{name: "ok", statusCode: http.StatusOK, expectErr: false},
		{name: "not found", statusCode: http.StatusNotFound, expectErr: true},
		{name: "server error", statusCode: http.StatusInternalServerError, expectErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var receivedMethod, receivedQuery string
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				receivedMethod, receivedQuery = r.Method, r.URL.RawQuery
				w.WriteHeader(tt.statusCode)
			}))
			defer server.Close()

			err := pushKumaHeartbeat(context.Background(), server.URL+"/api/push/abc?status=up&msg=OK")
			if (err != nil) != tt.expectErr {
				t.Errorf("pushKumaHeartbeat() error = %v, expectErr %v", err, tt.expectErr)
			}
			if receivedMethod != http.MethodGet {
				t.Errorf("method = %q, want %q", receivedMethod, http.MethodGet)
			}
			if receivedQuery != "status=up&msg=OK" {
				t.Errorf("query = %q, want the push URL query to be kept", receivedQuery)
			}
		})
	}
}

func TestPushKumaHeartbeatUnreachableServer(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	unreachableURL := server.URL
	server.Close()

	if err := pushKumaHeartbeat(context.Background(), unreachableURL); err == nil {
		t.Fatal("expected an error for an unreachable server, got nil")
	}
}

func TestSendKumaPushRespectsEnabledFlag(t *testing.T) {
	pushes := 0
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { pushes++ }))
	defer server.Close()

	originalEnabled, originalURL := KUMA_PUSH_ENABLED, KUMA_PUSH_URL
	t.Cleanup(func() { KUMA_PUSH_ENABLED, KUMA_PUSH_URL = originalEnabled, originalURL })
	KUMA_PUSH_URL = server.URL

	KUMA_PUSH_ENABLED = false
	sendKumaPush(context.Background())
	if pushes != 0 {
		t.Fatalf("pushes = %d while disabled, want 0", pushes)
	}

	KUMA_PUSH_ENABLED = true
	sendKumaPush(context.Background())
	if pushes != 1 {
		t.Fatalf("pushes = %d while enabled, want 1", pushes)
	}
}
