package main

import (
	"os"
	"strings"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// envDirEnv passes the folder with the .env file to the child process.
const envDirEnv = "COLLSTATNOT_TEST_ENV_DIR"

var testEnv = map[string]string{
	"MATTERMOST_WEBHOOK_URL":   "https://mattermost.example.com/hooks/abc",
	"FIREBASE_DATABASE_URL":    "https://demo-pnls-default-rtdb.firebaseio.com",
	"SENTRY_DSN":               "https://key@sentry.example.com/1",
	"DATADOG_API_KEY":          "api-key",
	"DATADOG_APP_KEY":          "app-key",
	"DATADOG_HEARTBEAT_METRIC": "pnls.heartbeat",
	"DATADOG_HOST":             "https://api.datadoghq.eu",
	"REDIS_URL":                "redis",
	"REDIS_PORT":               "6380",
	"REDIS_PASSWORD":           "password",
	"REDIS_DB":                 "2",
	"KUMA_PUSH_ENABLED":        " TRUE ",
	"KUMA_PUSH_URL":            "  http://uptime_kuma:3001/api/push/abc?status=up  ",
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
	loadFromEnvFile(t, testEnv)

	for name, variable := range configVariables() {
		want := strings.TrimSpace(testEnv[name])
		if name != "KUMA_PUSH_URL" {
			want = testEnv[name]
		}
		if *variable != want {
			t.Errorf("%s = %q, want %q", name, *variable, want)
		}
	}
	if !KUMA_PUSH_ENABLED {
		t.Error("KUMA_PUSH_ENABLED = false, want true")
	}
}

func TestLoadEnvVariablesWithoutKuma(t *testing.T) {
	loadFromEnvFile(t, map[string]string{"REDIS_URL": "redis"})

	if KUMA_PUSH_ENABLED || KUMA_PUSH_URL != "" {
		t.Errorf("expected the Kuma push off, got %v with %q", KUMA_PUSH_ENABLED, KUMA_PUSH_URL)
	}
}

// loadInChild runs loadEnvVariables in a child process, in the folder with the .env file.
func loadInChild(t *testing.T, values map[string]string) testutil.ChildResult {
	t.Helper()

	if testutil.InChild(t) {
		unsetConfigEnv(t)
		t.Chdir(os.Getenv(envDirEnv))
		loadEnvVariables()
		return testutil.ChildResult{}
	}
	return testutil.RunInChild(t, envDirEnv+"="+writeEnvFile(t, values))
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

func TestLoadEnvVariablesWithAnInvalidKumaFlagFatal(t *testing.T) {
	result := loadInChild(t, map[string]string{"KUMA_PUSH_ENABLED": "yes please"})
	if testutil.InChild(t) {
		return
	}

	want := `Fatal Error: KUMA_PUSH_ENABLED must be a boolean (true/false), got "yes please"`
	if result.ExitCode != 1 || !strings.Contains(result.Output(), want) {
		t.Fatalf("expected %q, got exit code %d:\n%s", want, result.ExitCode, result.Output())
	}
}

func TestLoadEnvVariablesWithKumaWithoutURLFatal(t *testing.T) {
	result := loadInChild(t, map[string]string{"KUMA_PUSH_ENABLED": "true", "KUMA_PUSH_URL": "  "})
	if testutil.InChild(t) {
		return
	}

	want := "Fatal Error: KUMA_PUSH_URL must be set when KUMA_PUSH_ENABLED is true"
	if result.ExitCode != 1 || !strings.Contains(result.Output(), want) {
		t.Fatalf("expected %q, got exit code %d:\n%s", want, result.ExitCode, result.Output())
	}
}

func TestSendMattermostMsgPostsAsTheService(t *testing.T) {
	logs := testutil.CaptureLog(t)
	webhook := useWebhook(t)

	sendMattermostMsg("Device `RPI-1` is back online.")

	message := webhook.OnlyMessage(t)
	if message["text"] != "Device `RPI-1` is back online." || message["username"] != SERVICE_NAME {
		t.Errorf("unexpected message %v", message)
	}
	if !strings.Contains(logs.String(), "Device `RPI-1` is back online.") {
		t.Errorf("expected the message in the log, got:\n%s", logs.String())
	}
}

func TestIsWorkingHoursMatchesTimezoneHourRule(t *testing.T) {
	now := common.GetTimeNow(TIMEZONE)
	expected := now.Hour() >= 6 && now.Hour() < 18

	if got := isWorkingHours(); got != expected {
		t.Fatalf("isWorkingHours() = %v, expected %v for hour %d", got, expected, now.Hour())
	}
}
