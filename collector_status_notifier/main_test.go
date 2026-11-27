package main

import (
	"context"
	"fmt"
	"maps"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func TestCheckDevicesStatusUsesDatadog(t *testing.T) {
	testutil.CaptureLog(t)
	datadog := useFakeDatadog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	kuma := useFakeKuma(t)
	now := time.Now()
	for _, device := range Devices {
		datadog.heartbeat(device, now)
	}
	firebase, client := newFakeFirebase(t, nil)

	checkDevicesStatus(context.Background(), client)

	if messages := texts(webhook); len(messages) != 0 {
		t.Fatalf("expected no alert, got %q", messages)
	}
	if len(firebase.Reads()) != 0 {
		t.Errorf("expected Firebase not to be read, got %q", firebase.Reads())
	}
	if kuma.count() != 1 {
		t.Errorf("Kuma pushes = %d, want 1", kuma.count())
	}
}

func TestCheckDevicesStatusFallsBackToFirebase(t *testing.T) {
	logs := testutil.CaptureLog(t)
	datadog := useFakeDatadog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	kuma := useFakeKuma(t)
	datadog.fail(DEVICE_RPI_1, http.StatusServiceUnavailable, "down")
	now := parisNow(t)
	_, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, now): status(now),
		statusNode(DEVICE_RPI_2, now): status(now),
		statusNode(DEVICE_RPI_3, now): status(now.Add(-time.Hour)),
	})

	checkDevicesStatus(context.Background(), client)

	if messages := texts(webhook); len(messages) != 1 || !strings.HasPrefix(messages[0], "Device `RPI-3` hasn't") {
		t.Fatalf("expected Firebase's alert for RPI-3, got %q", messages)
	}
	if !strings.Contains(logs.String(), "Datadog status check failed, falling back to Firebase status") {
		t.Errorf("expected the fallback in the log, got:\n%s", logs.String())
	}
	if kuma.count() != 1 {
		t.Errorf("Kuma pushes = %d, want 1", kuma.count())
	}
}

func TestCheckDevicesStatusUsesOneSourcePerDevice(t *testing.T) {
	testutil.CaptureLog(t)
	datadog := useFakeDatadog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	// Datadog sees RPI-1 now, then fails for RPI-2. Firebase's last write of RPI-1 is older.
	datadog.heartbeat(DEVICE_RPI_1, time.Now())
	datadog.fail(DEVICE_RPI_2, http.StatusInternalServerError, "down")
	now := parisNow(t)
	_, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, now): status(now.Add(-15 * time.Minute)),
		statusNode(DEVICE_RPI_2, now): status(now),
		statusNode(DEVICE_RPI_3, now): status(now),
	})

	checkDevicesStatus(context.Background(), client)

	messages := texts(webhook)
	reason := "a Datadog error for one device sends every device to Firebase, so the devices Datadog already " +
		"checked are checked again, and the sources can disagree."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if len(messages) != 0 {
			t.Errorf("expected no alert for RPI-1, which Datadog saw online, got %q", messages)
		}
	})
}

func TestCheckDevicesStatusDoesNotPushKumaWhenNoSourceAnswers(t *testing.T) {
	logs := testutil.CaptureLog(t)
	useFakeDatadog(t)
	DATADOG_HOST = testutil.RefusedURL()
	useMiniredis(t)
	useWebhook(t)
	kuma := useFakeKuma(t)
	firebase, client := newFakeFirebase(t, nil)
	firebase.FailReads(http.StatusForbidden)

	checkDevicesStatus(context.Background(), client)

	if !strings.Contains(logs.String(), "Error fetching status for node") {
		t.Fatalf("expected the Firebase errors in the log, got:\n%s", logs.String())
	}
	pushes := kuma.count()
	reason := "the Kuma heartbeat is sent after every check, even when neither Datadog nor Firebase answered, so " +
		"Uptime Kuma shows the service healthy while it checks nothing."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if pushes != 0 {
			t.Errorf("Kuma pushes = %d, want none", pushes)
		}
	})
}

func TestCheckDevicesStatusReportsAFailedCheckToSentry(t *testing.T) {
	testutil.CaptureLog(t)
	sentry := testutil.NewFakeSentry(t)
	logging.InitSentry(sentry.DSN(), SERVICE_NAME)
	t.Cleanup(func() { logging.InitSentry("", "") })
	useFakeDatadog(t)
	DATADOG_HOST = testutil.RefusedURL()
	useMiniredis(t)
	useWebhook(t)
	firebase, client := newFakeFirebase(t, nil)
	firebase.FailReads(http.StatusForbidden)

	checkDevicesStatus(context.Background(), client)

	reason := "failed Datadog and Firebase reads are only logged, so a check that sees no device is never reported."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, 2*time.Second); len(events) == 0 {
			t.Error("expected the failed check in Sentry")
		}
	})
}

// workDirEnv passes the folder main runs in to the child process.
const workDirEnv = "COLLSTATNOT_TEST_WORK_DIR"

// runMainInChild runs main in a child process, in the folder. main checks once, then waits 5 minutes for the next
// check, so the child ends when every device was checked once, or when main exits.
func runMainInChild(t *testing.T, dir string) testutil.ChildResult {
	t.Helper()

	if !testutil.InChild(t) {
		return testutil.RunInChild(t, workDirEnv+"="+dir)
	}

	unsetConfigEnv(t)
	t.Chdir(os.Getenv(workDirEnv))
	go main()

	// main sends the log to stdout and to its log file, which is read here.
	deadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(deadline) {
		time.Sleep(50 * time.Millisecond)
		logged, _ := os.ReadFile(LOG_FILE)
		if strings.Count(string(logged), "is online and has no offline cache state") == len(Devices) {
			// Leave time for the Kuma push, which follows the checks.
			time.Sleep(500 * time.Millisecond)
			os.Exit(0)
		}
	}
	fmt.Println("main neither checked the devices nor exited")
	os.Exit(3)
	return testutil.ChildResult{}
}

// serviceDir is a folder with the .env file and the Firebase credentials main reads.
func serviceDir(t *testing.T, values map[string]string, credentials string) string {
	t.Helper()

	env := map[string]string{"MATTERMOST_WEBHOOK_URL": "http://localhost:1/hooks/unused", "REDIS_DB": "0"}
	maps.Copy(env, values)
	dir := writeEnvFile(t, env)
	if credentials != "" {
		content, err := os.ReadFile(credentials)
		if err != nil {
			t.Fatalf("failed to read the credentials: %v", err)
		}
		if err := os.WriteFile(filepath.Join(dir, FIREBASE_CREDENTIALS_FILE), content, 0o600); err != nil {
			t.Fatalf("failed to write the credentials: %v", err)
		}
	}
	return dir
}

func TestMainChecksTheDevices(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "")
		return
	}
	datadog := newFakeDatadog(t)
	for _, device := range Devices {
		datadog.heartbeat(device, time.Now().Add(time.Minute))
	}
	redis := useMiniredis(t)
	webhook := testutil.NewFakeWebhook(t)
	kuma := useFakeKuma(t)
	firebase := testutil.NewFakeRealtimeDatabase(t, nil)
	host, port, _ := strings.Cut(redis.Addr(), ":")
	dir := serviceDir(t, map[string]string{
		"MATTERMOST_WEBHOOK_URL":   webhook.URL(),
		"FIREBASE_DATABASE_URL":    firebase.DatabaseURL(),
		"DATADOG_API_KEY":          "api-key",
		"DATADOG_APP_KEY":          "app-key",
		"DATADOG_HEARTBEAT_METRIC": "pnls.heartbeat",
		"DATADOG_HOST":             datadog.server.URL,
		"REDIS_URL":                host,
		"REDIS_PORT":               port,
		"KUMA_PUSH_ENABLED":        "true",
		"KUMA_PUSH_URL":            KUMA_PUSH_URL,
	}, firebase.CredentialsFile())

	result := runMainInChild(t, dir)

	if result.ExitCode != 0 {
		t.Fatalf("expected main to check the devices, got exit code %d:\n%s", result.ExitCode, result.Output())
	}
	if queries := datadog.received(); len(queries) != len(Devices) {
		t.Errorf("Datadog queries = %d, want one per device", len(queries))
	}
	if kuma.count() != 1 {
		t.Errorf("Kuma pushes = %d, want 1", kuma.count())
	}
	if messages := texts(webhook); len(messages) != 0 {
		t.Errorf("expected no alert, got %q", messages)
	}
	if !strings.Contains(result.Output(), "Checking devices status via Datadog...") {
		t.Errorf("expected the check in the output, got:\n%s", result.Output())
	}
}

func TestMainWithoutRedisFatal(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "")
		return
	}

	testCases := map[string]map[string]string{
		"Fatal Error: REDIS_URL is required": {},
		"Fatal Error: failed to connect to Redis": {
			"REDIS_URL":  "127.0.0.1",
			"REDIS_PORT": strings.TrimPrefix(testutil.RefusedURL(), "http://127.0.0.1:"),
		},
	}

	for want, values := range testCases {
		result := runMainInChild(t, serviceDir(t, values, ""))

		if result.ExitCode != 1 || !strings.Contains(result.Output(), want) {
			t.Errorf("expected %q and exit code 1, got %d:\n%s", want, result.ExitCode, result.Output())
		}
	}
}
