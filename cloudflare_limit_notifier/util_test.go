package main

import (
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// envDirEnv passes the folder with the .env file to the child process.
const envDirEnv = "CLIMNOT_TEST_ENV_DIR"

// configNames are the environment variables the service reads.
var configNames = []string{
	"MATTERMOST_WEBHOOK_URL", "SENTRY_DSN", "HTTP_PORT", "CHECK_ENDPOINT_PATH", "CLOUDFLARE_API_TOKEN",
	"CLOUDFLARE_GRAPHQL_ENDPOINT", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_R2_BUCKET_FILTER",
	"CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS", "CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS",
	"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS",
}

// restoreConfig puts the configuration variables back when the test ends.
func restoreConfig(t *testing.T) {
	t.Helper()

	webhook, sentry, token, account := MATTERMOST_WEBHOOK_URL, SENTRY_DSN, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
	endpoint, bucket, port, path := CLOUDFLARE_GRAPHQL_ENDPOINT, CLOUDFLARE_R2_BUCKET_FILTER, HTTP_PORT,
		CHECK_ENDPOINT_PATH
	attempts, delay, maxDelay := GRAPHQL_RETRY_ATTEMPTS, GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY
	t.Cleanup(func() {
		MATTERMOST_WEBHOOK_URL, SENTRY_DSN, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID = webhook, sentry, token, account
		CLOUDFLARE_GRAPHQL_ENDPOINT, CLOUDFLARE_R2_BUCKET_FILTER, HTTP_PORT, CHECK_ENDPOINT_PATH = endpoint, bucket,
			port, path
		GRAPHQL_RETRY_ATTEMPTS, GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY = attempts, delay, maxDelay
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

// loadFromEnvFile loads the configuration from a .env file with the values.
func loadFromEnvFile(t *testing.T, values map[string]string) {
	t.Helper()

	restoreConfig(t)
	unsetConfigEnv(t)
	t.Chdir(writeEnvFile(t, values))
	// godotenv sets the variables of the file in this process, so remove them again when the test ends.
	t.Cleanup(func() {
		for _, name := range configNames {
			_ = os.Unsetenv(name)
		}
	})
	loadEnvVariables()
}

func TestLoadEnvVariablesReadsEveryVariable(t *testing.T) {
	loadFromEnvFile(t, map[string]string{
		"MATTERMOST_WEBHOOK_URL":                     "https://mattermost.example.com/hooks/abc",
		"SENTRY_DSN":                                 "https://key@sentry.example.com/1",
		"HTTP_PORT":                                  " 9099 ",
		"CHECK_ENDPOINT_PATH":                        " r2/check ",
		"CLOUDFLARE_API_TOKEN":                       "token",
		"CLOUDFLARE_GRAPHQL_ENDPOINT":                "http://localhost:8787/graphql",
		"CLOUDFLARE_ACCOUNT_ID":                      "0123abcd",
		"CLOUDFLARE_R2_BUCKET_FILTER":                "pnls-charts",
		"CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS":          "3",
		"CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS":     "2",
		"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS": "10",
	})

	got := []any{
		MATTERMOST_WEBHOOK_URL, SENTRY_DSN, HTTP_PORT, CHECK_ENDPOINT_PATH, CLOUDFLARE_API_TOKEN,
		CLOUDFLARE_GRAPHQL_ENDPOINT, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_R2_BUCKET_FILTER, GRAPHQL_RETRY_ATTEMPTS,
		GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY,
	}
	want := []any{
		"https://mattermost.example.com/hooks/abc", "https://key@sentry.example.com/1", "9099", "/r2/check", "token",
		"http://localhost:8787/graphql", "0123abcd", "pnls-charts", uint(3), 2, 10,
	}
	names := []string{
		"MATTERMOST_WEBHOOK_URL", "SENTRY_DSN", "HTTP_PORT", "CHECK_ENDPOINT_PATH", "CLOUDFLARE_API_TOKEN",
		"CLOUDFLARE_GRAPHQL_ENDPOINT", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_R2_BUCKET_FILTER", "GRAPHQL_RETRY_ATTEMPTS",
		"GRAPHQL_RETRY_DELAY", "GRAPHQL_RETRY_MAX_DELAY",
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("%s = %#v, want %#v", names[i], got[i], want[i])
		}
	}
}

func TestLoadEnvVariablesDefaults(t *testing.T) {
	loadFromEnvFile(t, map[string]string{"HTTP_PORT": "9099"})

	if CLOUDFLARE_GRAPHQL_ENDPOINT != "https://api.cloudflare.com/client/v4/graphql" {
		t.Errorf("CLOUDFLARE_GRAPHQL_ENDPOINT = %q, want Cloudflare's API", CLOUDFLARE_GRAPHQL_ENDPOINT)
	}
	if CHECK_ENDPOINT_PATH != "/check" {
		t.Errorf("CHECK_ENDPOINT_PATH = %q, want /check", CHECK_ENDPOINT_PATH)
	}
	if GRAPHQL_RETRY_ATTEMPTS != 5 || GRAPHQL_RETRY_DELAY != 1 || GRAPHQL_RETRY_MAX_DELAY != 30 {
		t.Errorf("retries = %d attempts, %ds delay, %ds max delay, want 5, 1 and 30",
			GRAPHQL_RETRY_ATTEMPTS, GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY)
	}
	if CLOUDFLARE_R2_BUCKET_FILTER != "" {
		t.Errorf("CLOUDFLARE_R2_BUCKET_FILTER = %q, want no filter", CLOUDFLARE_R2_BUCKET_FILTER)
	}
}

func TestLoadEnvVariablesSpacesOnlyPathDefaultsToCheck(t *testing.T) {
	loadFromEnvFile(t, map[string]string{"CHECK_ENDPOINT_PATH": "   "})

	if CHECK_ENDPOINT_PATH != "/check" {
		t.Errorf("CHECK_ENDPOINT_PATH = %q, want /check", CHECK_ENDPOINT_PATH)
	}
}

func TestLoadEnvVariablesWithoutEnvFileFatal(t *testing.T) {
	if testutil.InChild(t) {
		unsetConfigEnv(t)
		t.Chdir(os.Getenv(envDirEnv))
		loadEnvVariables()
		return
	}

	result := testutil.RunInChild(t, envDirEnv+"="+t.TempDir())

	if result.ExitCode != 1 || !strings.Contains(result.Output(), "Fatal Error: Error loading .env file") {
		t.Fatalf("expected the missing .env file to end the service, got exit code %d:\n%s",
			result.ExitCode, result.Output())
	}
}

func TestLoadEnvVariablesWithInvalidRetrySettingsFatal(t *testing.T) {
	if testutil.InChild(t) {
		unsetConfigEnv(t)
		t.Chdir(os.Getenv(envDirEnv))
		loadEnvVariables()
		return
	}

	testCases := map[string]string{
		"CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS":          `CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS must be an integer, got "many"`,
		"CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS":     "CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS must be > 0, got 0",
		"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS": "CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS must be > 0, got -5",
	}
	values := map[string]string{
		"CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS":          "many",
		"CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS":     "0",
		"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS": "-5",
	}

	for name, wantErr := range testCases {
		result := testutil.RunInChild(t, envDirEnv+"="+writeEnvFile(t, map[string]string{name: values[name]}))

		if result.ExitCode != 1 || !strings.Contains(result.Output(), "Fatal Error: "+wantErr) {
			t.Errorf("with %s=%s: expected %q and exit code 1, got %d:\n%s",
				name, values[name], wantErr, result.ExitCode, result.Output())
		}
	}
}

// useValidConfig sets a configuration that passes validation until the test ends.
func useValidConfig(t *testing.T) {
	t.Helper()

	restoreConfig(t)
	MATTERMOST_WEBHOOK_URL = "https://mattermost.example.com/hooks/abc"
	CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID = "token", "0123abcd"
	HTTP_PORT, CHECK_ENDPOINT_PATH = "9099", "/check"
	GRAPHQL_RETRY_ATTEMPTS, GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY = 5, 1, 30
}

func TestValidateRequiredEnv(t *testing.T) {
	testCases := []struct {
		name    string
		change  func()
		wantErr string
	}{
		{name: "valid", change: func() {}},
		{name: "no token", change: func() { CLOUDFLARE_API_TOKEN = "" }, wantErr: "missing CLOUDFLARE_API_TOKEN"},
		{name: "no account", change: func() { CLOUDFLARE_ACCOUNT_ID = "" }, wantErr: "missing CLOUDFLARE_ACCOUNT_ID"},
		{name: "no port", change: func() { HTTP_PORT = "" }, wantErr: "missing HTTP_PORT"},
		{name: "no path", change: func() { CHECK_ENDPOINT_PATH = "" }, wantErr: "missing CHECK_ENDPOINT_PATH"},
		{
			name:   "max delay below the delay",
			change: func() { GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY = 5, 4 },
			wantErr: "CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS (4) must be >= " +
				"CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS (5)",
		},
		{name: "max delay equal to the delay", change: func() { GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY = 5, 5 }},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			useValidConfig(t)
			testCase.change()

			err := validateRequiredEnv()

			switch {
			case testCase.wantErr == "" && err != nil:
				t.Fatalf("unexpected error: %v", err)
			case testCase.wantErr != "" && (err == nil || err.Error() != testCase.wantErr):
				t.Fatalf("error = %v, want %q", err, testCase.wantErr)
			}
		})
	}
}

func TestValidateRequiredEnvRequiresTheWebhook(t *testing.T) {
	useValidConfig(t)
	MATTERMOST_WEBHOOK_URL = ""

	reason := "validateRequiredEnv doesn't check MATTERMOST_WEBHOOK_URL, so every check fails with 502 instead of " +
		"the service failing at startup."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if err := validateRequiredEnv(); err == nil || !strings.Contains(err.Error(), "MATTERMOST_WEBHOOK_URL") {
			t.Errorf("expected an error naming MATTERMOST_WEBHOOK_URL, got %v", err)
		}
	})
}

func TestGetPositiveIntEnv(t *testing.T) {
	testCases := []struct {
		name, value string
		set         bool
		want        int
		wantErr     string
	}{
		{name: "missing", want: 7},
		{name: "empty", set: true, value: "", want: 7},
		{name: "valid", set: true, value: "12", want: 12},
		{name: "not a number", set: true, value: "abc", wantErr: `TEST_POSITIVE_INT_ENV must be an integer, got "abc"`},
		{name: "with spaces", set: true, value: " 3 ", wantErr: `TEST_POSITIVE_INT_ENV must be an integer, got " 3 "`},
		{name: "zero", set: true, value: "0", wantErr: "TEST_POSITIVE_INT_ENV must be > 0, got 0"},
		{name: "negative", set: true, value: "-3", wantErr: "TEST_POSITIVE_INT_ENV must be > 0, got -3"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			const key = "TEST_POSITIVE_INT_ENV"
			t.Setenv(key, testCase.value)
			if !testCase.set {
				_ = os.Unsetenv(key)
			}

			got, err := getPositiveIntEnv(key, 7)

			if testCase.wantErr != "" {
				if err == nil || err.Error() != testCase.wantErr {
					t.Fatalf("error = %v, want %q", err, testCase.wantErr)
				}
				return
			}
			if err != nil || got != testCase.want {
				t.Fatalf("getPositiveIntEnv() = %d, %v, want %d", got, err, testCase.want)
			}
		})
	}
}

func TestGetPositiveUintEnv(t *testing.T) {
	const key = "TEST_POSITIVE_UINT_ENV"

	t.Setenv(key, "9")
	if got, err := getPositiveUintEnv(key, 4); err != nil || got != 9 {
		t.Errorf("getPositiveUintEnv() = %d, %v, want 9", got, err)
	}

	t.Setenv(key, "")
	if got, err := getPositiveUintEnv(key, 4); err != nil || got != 4 {
		t.Errorf("getPositiveUintEnv() = %d, %v, want the fallback 4", got, err)
	}

	t.Setenv(key, "-1")
	if got, err := getPositiveUintEnv(key, 4); err == nil || got != 0 {
		t.Errorf("getPositiveUintEnv() = %d, %v, want an error", got, err)
	}
}

func TestNormalizePath(t *testing.T) {
	testCases := []struct {
		name, path, want string
	}{
		{name: "keeps leading slash", path: "/check", want: "/check"},
		{name: "adds leading slash", path: "check", want: "/check"},
		{name: "trims and keeps the slash", path: "  /check  ", want: "/check"},
		{name: "trims and adds the slash", path: "  check  ", want: "/check"},
		{name: "nested path", path: "r2/check", want: "/r2/check"},
		{name: "empty stays empty", path: "", want: ""},
		{name: "spaces only become empty", path: "   ", want: ""},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			if got := normalizePath(testCase.path); got != testCase.want {
				t.Fatalf("normalizePath(%q) = %q, want %q", testCase.path, got, testCase.want)
			}
		})
	}
}

// withValues returns a copy of base with the values replaced.
func withValues(base, values map[string]string) map[string]string {
	merged := maps.Clone(base)
	maps.Copy(merged, values)
	return merged
}
