package main

import (
	"fmt"
	"io"
	"maps"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// useTestConfig points the handler at a readable path and the given Mattermost webhook for the duration of a test.
func useTestConfig(t *testing.T, webhookURL string) {
	t.Helper()

	restoreConfig(t)
	MATTERMOST_WEBHOOK_URL = webhookURL
	DISK_MOUNT_PATH = t.TempDir()
}

// useFakeSentry sends the test's Sentry events to a fake server, and turns Sentry off when the test ends.
func useFakeSentry(t *testing.T) *testutil.FakeSentry {
	t.Helper()

	sentry := testutil.NewFakeSentry(t)
	logging.InitSentry(sentry.DSN(), SERVICE_NAME)
	t.Cleanup(func() { logging.InitSentry("", SERVICE_NAME) })
	return sentry
}

func postCheck(t *testing.T) *httptest.ResponseRecorder {
	t.Helper()

	recorder := httptest.NewRecorder()
	checkDiskAndNotifyHandler(recorder, httptest.NewRequest(http.MethodPost, "/check", http.NoBody))
	return recorder
}

func TestCheckDiskAndNotifyHandlerRejectsOtherMethods(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	useTestConfig(t, webhook.URL())

	for _, method := range []string{http.MethodGet, http.MethodHead, http.MethodPut, http.MethodDelete} {
		recorder := httptest.NewRecorder()
		checkDiskAndNotifyHandler(recorder, httptest.NewRequest(method, "/check", http.NoBody))

		if recorder.Code != http.StatusMethodNotAllowed {
			t.Errorf("%s: status = %d, want %d", method, recorder.Code, http.StatusMethodNotAllowed)
		}
	}
	if messages := webhook.Messages(); len(messages) != 0 {
		t.Errorf("expected no report for the rejected requests, got %v", messages)
	}
}

func TestCheckDiskAndNotifyHandlerNamesTheAllowedMethod(t *testing.T) {
	recorder := httptest.NewRecorder()
	checkDiskAndNotifyHandler(recorder, httptest.NewRequest(http.MethodGet, "/check", http.NoBody))

	testutil.ExpectFailure(t, "The 405 reply has no Allow header.", func(t testutil.TB) {
		if got := recorder.Header().Get("Allow"); got != http.MethodPost {
			t.Errorf("Allow = %q, want %q", got, http.MethodPost)
		}
	})
}

func TestCheckDiskAndNotifyHandlerSendsReport(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	useTestConfig(t, webhook.URL())

	recorder := postCheck(t)

	if recorder.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusOK)
	}
	if body := recorder.Body.String(); body != "Disk usage check sent to Mattermost info channel." {
		t.Errorf("unexpected body %q", body)
	}

	messages := webhook.Messages()
	if len(messages) != 1 {
		t.Fatalf("reports sent = %d, want 1", len(messages))
	}
	if messages[0]["username"] != SERVICE_NAME {
		t.Errorf("username = %v, want %q", messages[0]["username"], SERVICE_NAME)
	}
	if icon, _ := messages[0]["icon_url"].(string); !strings.HasSuffix(icon, "/limit_notifier.png") {
		t.Errorf("icon_url = %v, want the limit notifier icon", messages[0]["icon_url"])
	}
	text, _ := messages[0]["text"].(string)
	for _, want := range []string{"* Mount path: `" + DISK_MOUNT_PATH + "`\n", "* Used: ", " GB (", "%)\n* Free: "} {
		if !strings.Contains(text, want) {
			t.Errorf("expected %q in the report, got:\n%s", want, text)
		}
	}
}

func TestCheckDiskAndNotifyHandlerDiskFailure(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	useTestConfig(t, webhook.URL())
	DISK_MOUNT_PATH = filepath.Join(t.TempDir(), "unmounted")

	recorder := postCheck(t)

	if recorder.Code != http.StatusInternalServerError {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusInternalServerError)
	}
	if body := strings.TrimSpace(recorder.Body.String()); body != "Failed to check disk usage" {
		t.Errorf("unexpected body %q", body)
	}
	if messages := webhook.Messages(); len(messages) != 0 {
		t.Errorf("expected no report when the disk can't be read, got %v", messages)
	}
}

func TestCheckDiskAndNotifyHandlerReportsMattermostFailure(t *testing.T) {
	useTestConfig(t, testutil.RefusedURL())

	// The handler must answer with an error and keep serving requests when Mattermost refuses the connection
	for attempt := 1; attempt <= 2; attempt++ {
		recorder := postCheck(t)

		if recorder.Code != http.StatusBadGateway {
			t.Errorf("attempt %d: status = %d, want %d", attempt, recorder.Code, http.StatusBadGateway)
		}
	}
}

func TestCheckDiskAndNotifyHandlerMattermostErrorReply(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	webhook.Answer(http.StatusInternalServerError, "")
	useTestConfig(t, webhook.URL())

	recorder := postCheck(t)

	if recorder.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
	if body := strings.TrimSpace(recorder.Body.String()); body != "Failed to send disk usage report to Mattermost" {
		t.Errorf("unexpected body %q", body)
	}
}

func TestCheckDiskAndNotifyHandlerDiskFailureIsReportedToSentry(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	useTestConfig(t, webhook.URL())
	DISK_MOUNT_PATH = filepath.Join(t.TempDir(), "unmounted")
	sentry := useFakeSentry(t)

	postCheck(t)

	testutil.ExpectFailure(t, "A failed disk check is only logged, not sent to Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) == 0 {
			t.Error("expected the failure in Sentry, got no event")
		}
	})
}

func TestCheckDiskAndNotifyHandlerMattermostFailureIsReportedToSentry(t *testing.T) {
	webhook := testutil.NewFakeWebhook(t)
	webhook.Answer(http.StatusInternalServerError, "")
	useTestConfig(t, webhook.URL())
	sentry := useFakeSentry(t)

	postCheck(t)

	reason := "A report Mattermost didn't take is only logged, not sent to Sentry."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) == 0 {
			t.Error("expected the failure in Sentry, got no event")
		}
	})
}

// freePort returns a TCP port that nothing listens on.
func freePort(t *testing.T) string {
	t.Helper()

	listener, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatalf("failed to find a free port: %v", err)
	}
	defer listener.Close()
	return strconv.Itoa(listener.Addr().(*net.TCPAddr).Port)
}

// writeServiceEnv writes the .env file main reads, with the given values replacing the defaults.
func writeServiceEnv(t *testing.T, values map[string]string) string {
	t.Helper()

	config := map[string]string{
		"MATTERMOST_WEBHOOK_URL": "http://localhost:1/hooks/unused",
		"SENTRY_DSN":             "",
		"HTTP_PORT":              freePort(t),
		"CHECK_ENDPOINT_PATH":    "/check",
		"DISK_MOUNT_PATH":        t.TempDir(),
	}
	maps.Copy(config, values)

	var content strings.Builder
	for _, name := range configNames {
		fmt.Fprintf(&content, "%s=%s\n", name, config[name])
	}
	return writeEnvFile(t, content.String())
}

// checkURLEnv passes the URL of the check to the child process.
const checkURLEnv = "HSLIMNOT_TEST_CHECK_URL"

// runMainInChild runs main in a child process, in the folder with the .env file. With a check URL, the child sends one
// check once the server is up and prints the reply; without one, it waits for main to exit.
func runMainInChild(t *testing.T, envDir, checkURL string) testutil.ChildResult {
	t.Helper()

	if !testutil.InChild(t) {
		return testutil.RunInChild(t, envDirEnv+"="+envDir, checkURLEnv+"="+checkURL)
	}

	unsetConfigEnv(t)
	t.Chdir(os.Getenv(envDirEnv))
	go main()

	checkURL = os.Getenv(checkURLEnv)
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		time.Sleep(20 * time.Millisecond)
		if checkURL == "" {
			continue
		}
		response, err := http.Post(checkURL, "text/plain", http.NoBody)
		if err != nil {
			continue
		}
		body, _ := io.ReadAll(response.Body)
		_ = response.Body.Close()
		fmt.Printf("reply: %d %s\n", response.StatusCode, body)
		return testutil.ChildResult{}
	}
	fmt.Println("main neither served the check nor exited")
	return testutil.ChildResult{}
}

func TestMainServesTheCheck(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	webhook := testutil.NewFakeWebhook(t)
	port := freePort(t)
	// The path is written without its leading slash, as normalizePath adds it.
	envDir := writeServiceEnv(t, map[string]string{
		"MATTERMOST_WEBHOOK_URL": webhook.URL(),
		"HTTP_PORT":              port,
		"CHECK_ENDPOINT_PATH":    "home/check",
	})

	result := runMainInChild(t, envDir, "http://localhost:"+port+"/home/check")

	if !strings.Contains(result.Stdout, "reply: 200 Disk usage check sent to Mattermost info channel.") {
		t.Fatalf("expected the check to succeed, got:\n%s", result.Output())
	}
	if !strings.Contains(result.Output(), SERVICE_NAME+" listening on :") {
		t.Errorf("expected the start to be logged, got:\n%s", result.Output())
	}
	if messages := webhook.Messages(); len(messages) != 1 {
		t.Errorf("reports sent = %d, want 1", len(messages))
	}
}

func TestMainWithMissingConfigurationFatal(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	for _, name := range []string{"MATTERMOST_WEBHOOK_URL", "HTTP_PORT", "CHECK_ENDPOINT_PATH", "DISK_MOUNT_PATH"} {
		result := runMainInChild(t, writeServiceEnv(t, map[string]string{name: ""}), "")

		if result.ExitCode != 1 {
			t.Errorf("without %s: expected exit code 1, got %d:\n%s", name, result.ExitCode, result.Output())
		}
		if want := "Fatal Error: Invalid configuration: missing " + name; !strings.Contains(result.Output(), want) {
			t.Errorf("without %s: expected %q in the output, got:\n%s", name, want, result.Output())
		}
	}
}

func TestMainWithPortInUseFatal(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	listener, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatalf("failed to take a port: %v", err)
	}
	defer listener.Close()
	port := strconv.Itoa(listener.Addr().(*net.TCPAddr).Port)

	result := runMainInChild(t, writeServiceEnv(t, map[string]string{"HTTP_PORT": port}), "")

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: HTTP server failed: listen tcp :"+port) {
		t.Fatalf("expected the failed listen to be logged, got:\n%s", result.Output())
	}
}
