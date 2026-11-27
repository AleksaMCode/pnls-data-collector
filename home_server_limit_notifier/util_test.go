package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/shirou/gopsutil/v4/disk"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// envDirEnv passes the folder with the .env file to the child process.
const envDirEnv = "HSLIMNOT_TEST_ENV_DIR"

var configNames = []string{
	"MATTERMOST_WEBHOOK_URL",
	"SENTRY_DSN",
	"HTTP_PORT",
	"CHECK_ENDPOINT_PATH",
	"DISK_MOUNT_PATH",
}

// restoreConfig puts the configuration variables back when the test ends.
func restoreConfig(t *testing.T) {
	t.Helper()

	webhookURL, sentryDSN, port, endpointPath, mountPath := MATTERMOST_WEBHOOK_URL, SENTRY_DSN, HTTP_PORT,
		CHECK_ENDPOINT_PATH, DISK_MOUNT_PATH
	t.Cleanup(func() {
		MATTERMOST_WEBHOOK_URL, SENTRY_DSN, HTTP_PORT, CHECK_ENDPOINT_PATH, DISK_MOUNT_PATH = webhookURL, sentryDSN,
			port, endpointPath, mountPath
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

// writeEnvFile writes a .env file with the given content into a new folder and returns the folder.
func writeEnvFile(t *testing.T, content string) string {
	t.Helper()

	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, ".env"), []byte(content), 0o600); err != nil {
		t.Fatalf("failed to write the .env file: %v", err)
	}
	return dir
}

func TestLoadEnvVariablesReadsTheEnvFile(t *testing.T) {
	restoreConfig(t)
	unsetConfigEnv(t)
	t.Chdir(writeEnvFile(t, strings.Join([]string{
		"MATTERMOST_WEBHOOK_URL=  https://mattermost.example.com/hooks/abc  ",
		"SENTRY_DSN= https://key@sentry.example.com/1 ",
		"HTTP_PORT= 9092",
		"CHECK_ENDPOINT_PATH=  check  ",
		"DISK_MOUNT_PATH= / ",
	}, "\n")))

	loadEnvVariables()

	want := map[string]string{
		"MATTERMOST_WEBHOOK_URL": "https://mattermost.example.com/hooks/abc",
		"SENTRY_DSN":             "https://key@sentry.example.com/1",
		"HTTP_PORT":              "9092",
		"CHECK_ENDPOINT_PATH":    "/check",
		"DISK_MOUNT_PATH":        "/",
	}
	got := map[string]string{
		"MATTERMOST_WEBHOOK_URL": MATTERMOST_WEBHOOK_URL,
		"SENTRY_DSN":             SENTRY_DSN,
		"HTTP_PORT":              HTTP_PORT,
		"CHECK_ENDPOINT_PATH":    CHECK_ENDPOINT_PATH,
		"DISK_MOUNT_PATH":        DISK_MOUNT_PATH,
	}
	for name, value := range want {
		if got[name] != value {
			t.Errorf("%s = %q, want %q", name, got[name], value)
		}
	}
}

func TestLoadEnvVariablesKeepsAnEmptyEndpointPathEmpty(t *testing.T) {
	restoreConfig(t)
	unsetConfigEnv(t)
	t.Chdir(writeEnvFile(t, "CHECK_ENDPOINT_PATH=   \n"))

	loadEnvVariables()

	if CHECK_ENDPOINT_PATH != "" {
		t.Fatalf("CHECK_ENDPOINT_PATH = %q, want it empty so the validation reports it", CHECK_ENDPOINT_PATH)
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

func TestValidateRequiredEnv(t *testing.T) {
	testCases := []struct {
		name    string
		missing string
		wantErr string
	}{
		{name: "complete configuration", wantErr: ""},
		{name: "Sentry is optional", missing: "SENTRY_DSN", wantErr: ""},
		{name: "missing webhook", missing: "MATTERMOST_WEBHOOK_URL", wantErr: "missing MATTERMOST_WEBHOOK_URL"},
		{name: "missing port", missing: "HTTP_PORT", wantErr: "missing HTTP_PORT"},
		{name: "missing endpoint path", missing: "CHECK_ENDPOINT_PATH", wantErr: "missing CHECK_ENDPOINT_PATH"},
		{name: "missing mount path", missing: "DISK_MOUNT_PATH", wantErr: "missing DISK_MOUNT_PATH"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			restoreConfig(t)
			MATTERMOST_WEBHOOK_URL = "https://mattermost.example.com/hooks/abc"
			SENTRY_DSN = "https://key@sentry.example.com/1"
			HTTP_PORT = "9092"
			CHECK_ENDPOINT_PATH = "/check"
			DISK_MOUNT_PATH = "/"
			config := map[string]*string{
				"MATTERMOST_WEBHOOK_URL": &MATTERMOST_WEBHOOK_URL,
				"SENTRY_DSN":             &SENTRY_DSN,
				"HTTP_PORT":              &HTTP_PORT,
				"CHECK_ENDPOINT_PATH":    &CHECK_ENDPOINT_PATH,
				"DISK_MOUNT_PATH":        &DISK_MOUNT_PATH,
			}
			if variable, ok := config[testCase.missing]; ok {
				*variable = ""
			}

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

func TestNormalizePath(t *testing.T) {
	testCases := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "empty path stays empty",
			input:    "",
			expected: "",
		},
		{
			name:     "whitespace path stays empty",
			input:    "   ",
			expected: "",
		},
		{
			name:     "already normalized path remains unchanged",
			input:    "/check",
			expected: "/check",
		},
		{
			name:     "missing leading slash gets prefixed",
			input:    "check",
			expected: "/check",
		},
		{
			name:     "trimmed path without leading slash gets prefixed",
			input:    "  trigger  ",
			expected: "/trigger",
		},
		{
			name:     "nested path gets prefixed",
			input:    "api/check",
			expected: "/api/check",
		},
		{
			name:     "root path remains unchanged",
			input:    "/",
			expected: "/",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			actual := normalizePath(testCase.input)
			if actual != testCase.expected {
				t.Fatalf("normalizePath(%q) = %q, expected %q", testCase.input, actual, testCase.expected)
			}
		})
	}
}

func TestGetDiskUsageMatchesTheFilesystem(t *testing.T) {
	mountPath := t.TempDir()

	usage, err := getDiskUsage(mountPath)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	stats, err := disk.Usage(mountPath)
	if err != nil {
		t.Fatalf("failed to read the disk usage in the test: %v", err)
	}

	if usage.TotalBytes <= 0 || usage.TotalBytes != float64(stats.Total) {
		t.Errorf("TotalBytes = %v, want %d", usage.TotalBytes, stats.Total)
	}
	if usage.UsedBytes < 0 || usage.FreeBytes < 0 {
		t.Errorf("expected no negative sizes, got %+v", usage)
	}
	if usage.UsedBytes+usage.FreeBytes != usage.TotalBytes {
		t.Errorf("used + free = %v, want the total %v", usage.UsedBytes+usage.FreeBytes, usage.TotalBytes)
	}
}

func TestGetDiskUsageMissingPath(t *testing.T) {
	mountPath := filepath.Join(t.TempDir(), "unmounted")

	usage, err := getDiskUsage(mountPath)

	if err == nil {
		t.Fatalf("expected an error, got %+v", usage)
	}
	if !strings.Contains(err.Error(), "failed to read disk usage for "+mountPath) {
		t.Errorf("expected the path in the error, got %q", err)
	}
	if usage != (diskUsage{}) {
		t.Errorf("expected an empty usage with the error, got %+v", usage)
	}
}

func TestGetDiskUsageLeavesOutReservedSpace(t *testing.T) {
	mountPath := t.TempDir()
	stats, err := disk.Usage(mountPath)
	if err != nil {
		t.Fatalf("failed to read the disk usage in the test: %v", err)
	}
	// The space in use can change between the two reads, so the check below allows 1 MB.
	const tolerance = 1 << 20
	// The bug only shows when the reserved space is larger than that, even after the usage moves by up to 1 MB
	// between the reads. With less, the check can't tell the bug from a fix.
	if reserved := float64(stats.Total-stats.Free) - float64(stats.Used); reserved <= 2*tolerance {
		t.Skipf("this filesystem reserves %.0f bytes for root, too little for the bug to show here", reserved)
	}

	usage, err := getDiskUsage(mountPath)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	reason := "getDiskUsage counts the space reserved for root as used, so the report shows more than df."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if diff := usage.UsedBytes - float64(stats.Used); diff > tolerance || diff < -tolerance {
			t.Errorf("UsedBytes = %.0f, want %d as df shows", usage.UsedBytes, stats.Used)
		}
	})
}

func TestFormatUsageMessage(t *testing.T) {
	const gb = 1024 * 1024 * 1024

	testCases := []struct {
		name     string
		usage    diskUsage
		expected string
	}{
		{
			name:  "partly used disk",
			usage: diskUsage{UsedBytes: 30 * gb, FreeBytes: 70 * gb, TotalBytes: 100 * gb},
			expected: "* Mount path: `/`\n* Used: 30.00 GB / 100.00 GB (30.00%)\n" +
				"* Free: 70.00 GB",
		},
		{
			name:     "full disk",
			usage:    diskUsage{UsedBytes: 64 * gb, FreeBytes: 0, TotalBytes: 64 * gb},
			expected: "* Mount path: `/`\n* Used: 64.00 GB / 64.00 GB (100.00%)\n* Free: 0.00 GB",
		},
		{
			name:     "empty disk",
			usage:    diskUsage{UsedBytes: 0, FreeBytes: 32 * gb, TotalBytes: 32 * gb},
			expected: "* Mount path: `/`\n* Used: 0.00 GB / 32.00 GB (0.00%)\n* Free: 32.00 GB",
		},
		{
			name:     "sizes are rounded to two decimals",
			usage:    diskUsage{UsedBytes: gb / 3, FreeBytes: 2 * gb / 3, TotalBytes: gb},
			expected: "* Mount path: `/`\n* Used: 0.33 GB / 1.00 GB (33.33%)\n* Free: 0.67 GB",
		},
		{
			name:     "gigabytes are 1024³ bytes",
			usage:    diskUsage{UsedBytes: 1e9, FreeBytes: 1e9, TotalBytes: 2e9},
			expected: "* Mount path: `/`\n* Used: 0.93 GB / 1.86 GB (50.00%)\n* Free: 0.93 GB",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			message := formatUsageMessage(testCase.usage, "/")

			// The heading is left out: it says "memory" for disk usage, a known wording issue.
			heading, details, found := strings.Cut(message, "\n")
			if !found || !strings.HasPrefix(heading, "Home server ") {
				t.Fatalf("expected a heading line, got %q", message)
			}
			if details != testCase.expected {
				t.Fatalf("got:\n%s\nwant:\n%s", details, testCase.expected)
			}
		})
	}
}

func TestFormatUsageMessageShowsTheMountPath(t *testing.T) {
	message := formatUsageMessage(diskUsage{UsedBytes: 1, FreeBytes: 1, TotalBytes: 2}, "/mnt/ssd")

	if !strings.Contains(message, "* Mount path: `/mnt/ssd`\n") {
		t.Fatalf("expected the mount path in the message, got:\n%s", message)
	}
}
