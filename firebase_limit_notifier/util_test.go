package main

import (
	"encoding/json"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// envDirEnv passes the folder with the .env file to the child process.
const envDirEnv = "FBLIMNOT_TEST_ENV_DIR"

// configVariables are the configuration variables, by the name of their environment variable.
func configVariables() map[string]*string {
	return map[string]*string{
		"MATTERMOST_WEBHOOK_URL": &MATTERMOST_WEBHOOK_URL,
		"FIREBASE_DATABASE_URL":  &FIREBASE_DATABASE_URL,
		"SENTRY_DSN":             &SENTRY_DSN,
		"R2_ACCESS_KEY":          &R2_ACCESS_KEY,
		"R2_SECRET_KEY":          &R2_SECRET_KEY,
		"R2_BUCKET_NAME":         &R2_BUCKET_NAME,
		"CLOUDFLARE_ACCOUNT_ID":  &CLOUDFLARE_ACCOUNT_ID,
		"R2_BUCKET_PUBLIC_URL":   &R2_BUCKET_PUBLIC_URL,
		"R2_ENDPOINT":            &R2_ENDPOINT,
		"HTTP_PORT":              &HTTP_PORT,
		"CHECK_ENDPOINT_PATH":    &CHECK_ENDPOINT_PATH,
	}
}

// restoreConfig puts the configuration variables back when the test ends.
func restoreConfig(t *testing.T) {
	t.Helper()

	saved := map[string]string{}
	for name, variable := range configVariables() {
		saved[name] = *variable
	}
	t.Cleanup(func() {
		for name, variable := range configVariables() {
			*variable = saved[name]
		}
	})
}

// unsetConfigEnv removes the configuration from the environment until the test ends, as godotenv doesn't replace
// variables that are already set.
func unsetConfigEnv(t *testing.T) {
	t.Helper()

	for name := range configVariables() {
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
	for name, value := range values {
		fmt.Fprintf(&content, "%s=%s\n", name, value)
	}
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, ".env"), []byte(content.String()), 0o600); err != nil {
		t.Fatalf("failed to write the .env file: %v", err)
	}
	return dir
}

var testEnv = map[string]string{
	"MATTERMOST_WEBHOOK_URL": "https://mattermost.example.com/hooks/abc",
	"FIREBASE_DATABASE_URL":  "https://demo-pnls-default-rtdb.firebaseio.com",
	"SENTRY_DSN":             "https://key@sentry.example.com/1",
	"R2_ACCESS_KEY":          "access-key",
	"R2_SECRET_KEY":          "secret-key",
	"R2_BUCKET_NAME":         "pnls-charts",
	"CLOUDFLARE_ACCOUNT_ID":  "account-id",
	"R2_BUCKET_PUBLIC_URL":   "https://pub-charts.r2.dev",
	"R2_ENDPOINT":            "http://localhost:9000",
	"HTTP_PORT":              "9093",
	"CHECK_ENDPOINT_PATH":    "/check",
}

func TestLoadEnvVariablesReadsEveryVariable(t *testing.T) {
	restoreConfig(t)
	unsetConfigEnv(t)
	t.Chdir(writeEnvFile(t, testEnv))

	loadEnvVariables()

	for name, variable := range configVariables() {
		if *variable != testEnv[name] {
			t.Errorf("%s = %q, want %q", name, *variable, testEnv[name])
		}
	}
}

func TestLoadEnvVariablesEndpointPath(t *testing.T) {
	testCases := []struct {
		name     string
		value    string
		expected string
	}{
		{name: "defaults to /check", value: "", expected: "/check"},
		{name: "spaces only default to /check", value: "   ", expected: "/check"},
		{name: "gets a leading slash", value: "usage", expected: "/usage"},
		{name: "is trimmed", value: "  /usage  ", expected: "/usage"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			restoreConfig(t)
			unsetConfigEnv(t)
			env := maps.Clone(testEnv)
			env["CHECK_ENDPOINT_PATH"] = testCase.value
			env["HTTP_PORT"] = " 9093 "
			t.Chdir(writeEnvFile(t, env))

			loadEnvVariables()

			if CHECK_ENDPOINT_PATH != testCase.expected {
				t.Errorf("CHECK_ENDPOINT_PATH = %q, want %q", CHECK_ENDPOINT_PATH, testCase.expected)
			}
			if HTTP_PORT != "9093" {
				t.Errorf("HTTP_PORT = %q, want it trimmed", HTTP_PORT)
			}
		})
	}
}

func TestLoadEnvVariablesWithoutEnvFileFatal(t *testing.T) {
	if testutil.InChild(t) {
		t.Chdir(os.Getenv(envDirEnv))
		loadEnvVariables()
		return
	}

	result := testutil.RunInChild(t, envDirEnv+"="+t.TempDir())

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: Error loading .env file") {
		t.Fatalf("expected the missing .env file to be logged, got:\n%s", result.Output())
	}
}

func TestBytesToMB(t *testing.T) {
	tests := []struct {
		name     string
		bytes    int
		expected float64
	}{
		{
			name:     "zero bytes",
			bytes:    0,
			expected: 0,
		},
		{
			name:     "one MB",
			bytes:    1024 * 1024,
			expected: 1,
		},
		{
			name:     "half MB",
			bytes:    512 * 1024,
			expected: 0.5,
		},
		{
			name:     "two MB",
			bytes:    2 * 1024 * 1024,
			expected: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := bytesToMB(tt.bytes)
			if result != tt.expected {
				t.Errorf("bytesToMB(%d) = %f, want %f", tt.bytes, result, tt.expected)
			}
		})
	}
}

func TestGetNodeSize(t *testing.T) {
	tests := []struct {
		name string
		node any
	}{
		{
			name: "simple map",
			node: map[string]any{
				"id":   123,
				"name": "node1",
			},
		},
		{
			name: "nested structure",
			node: map[string]any{
				"id": 1,
				"metadata": map[string]any{
					"region": "us-east-1",
					"active": true,
				},
			},
		},
		{
			name: "slice of objects",
			node: []map[string]any{
				{"a": 1},
				{"b": 2},
			},
		},
		{
			name: "struct input",
			node: struct {
				ID   int    `json:"id"`
				Name string `json:"name"`
			}{
				ID:   10,
				Name: "test",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Marshal manually to calculate expected size
			b, err := json.Marshal(tt.node)
			if err != nil {
				t.Fatalf("json.Marshal failed: %v", err)
			}

			expected := float64(len(b)) / (1024 * 1024)
			result, _ := getNodeSize(tt.node)

			if result != expected {
				t.Errorf("getNodeSize() = %f, want %f", result, expected)
			}
		})
	}
}

func TestGetNodeSizeCountsTheBytesOfTheJSON(t *testing.T) {
	tests := []struct {
		name  string
		node  any
		bytes int
	}{
		// A node that doesn't exist reads as nil, which is sent as null.
		{name: "missing node", node: nil, bytes: len("null")},
		{name: "exact object", node: map[string]any{"ssid": "PNLS"}, bytes: len(`{"ssid":"PNLS"}`)},
		// Text is counted in UTF-8 bytes, not in characters.
		{name: "non-ASCII text", node: "Šabac", bytes: len(`"Šabac"`)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			size, err := getNodeSize(tt.node)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if want := float64(tt.bytes) / BYTES_IN_MB; size != want {
				t.Errorf("getNodeSize(%v) = %v MB, want %d bytes", tt.node, size, tt.bytes)
			}
		})
	}
}

func TestGetNodeSizeInvalidInput(t *testing.T) {
	_, err := getNodeSize(func() {})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestNormalizePath(t *testing.T) {
	tests := []struct {
		name     string
		path     string
		expected string
	}{
		{name: "empty", path: "", expected: ""},
		{name: "only spaces", path: "   ", expected: ""},
		{name: "already has slash", path: "/check", expected: "/check"},
		{name: "missing slash", path: "check", expected: "/check"},
		{name: "surrounding spaces", path: "  check ", expected: "/check"},
		{name: "nested path", path: "api/check", expected: "/api/check"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if result := normalizePath(tt.path); result != tt.expected {
				t.Errorf("normalizePath(%q) = %q, want %q", tt.path, result, tt.expected)
			}
		})
	}
}

func TestValidateRequiredEnv(t *testing.T) {
	tests := []struct {
		name    string
		port    string
		path    string
		wantErr string
	}{
		{name: "valid", port: "9093", path: "/check", wantErr: ""},
		{name: "missing port", port: "", path: "/check", wantErr: "missing HTTP_PORT"},
		{name: "missing path", port: "9093", path: "", wantErr: "missing CHECK_ENDPOINT_PATH"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			restoreConfig(t)
			HTTP_PORT, CHECK_ENDPOINT_PATH = tt.port, tt.path

			err := validateRequiredEnv()

			switch {
			case tt.wantErr == "" && err != nil:
				t.Fatalf("unexpected error: %v", err)
			case tt.wantErr != "" && (err == nil || err.Error() != tt.wantErr):
				t.Fatalf("error = %v, want %q", err, tt.wantErr)
			}
		})
	}
}

func TestValidateRequiredEnvChecksTheServices(t *testing.T) {
	for _, name := range []string{"MATTERMOST_WEBHOOK_URL", "FIREBASE_DATABASE_URL", "R2_BUCKET_NAME"} {
		t.Run(name, func(t *testing.T) {
			restoreConfig(t)
			for variableName, variable := range configVariables() {
				*variable = testEnv[variableName]
			}
			*configVariables()[name] = ""

			reason := "validateRequiredEnv only checks HTTP_PORT and CHECK_ENDPOINT_PATH."
			testutil.ExpectFailure(t, reason, func(t testutil.TB) {
				if err := validateRequiredEnv(); err == nil || !strings.Contains(err.Error(), name) {
					t.Errorf("expected an error naming %s, got %v", name, err)
				}
			})
		})
	}
}
