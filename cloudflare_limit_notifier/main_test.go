package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// useTestWebhook sends the reports to a fake Mattermost webhook until the test ends.
func useTestWebhook(t *testing.T) *testutil.FakeWebhook {
	t.Helper()

	webhook := testutil.NewFakeWebhook(t)
	restoreConfig(t)
	MATTERMOST_WEBHOOK_URL = webhook.URL()
	return webhook
}

func check(method string) *httptest.ResponseRecorder {
	recorder := httptest.NewRecorder()
	checkCloudflareUsageAndNotifyHandler(recorder, httptest.NewRequest(method, CHECK_PATH, http.NoBody))
	return recorder
}

func TestSendUsageReportFormatsTheUsage(t *testing.T) {
	testutil.CaptureLog(t)
	webhook := useTestWebhook(t)

	err := sendUsageReport(usageMetrics{
		ClassARequests: 123_456,
		ClassBRequests: 2_500_000,
		StorageBytes:   2.5 * BYTES_IN_GB,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	message := webhook.OnlyMessage(t)
	want := "R2 monthly usage:\n" +
		"* Storage: 2.50 GB / 10 GB (25.00%)\n" +
		"* Operations:\n" +
		"  - Class A: 123,456 / 1,000,000 (12.35%)\n" +
		"  - Class B: 2,500,000 / 10,000,000 (25.00%)"
	if message["text"] != want {
		t.Errorf("text =\n%v\nwant\n%s", message["text"], want)
	}
	if message["username"] != SERVICE_NAME {
		t.Errorf("username = %v, want %q", message["username"], SERVICE_NAME)
	}
}

func TestSendUsageReportWithoutUsage(t *testing.T) {
	testutil.CaptureLog(t)
	webhook := useTestWebhook(t)

	if err := sendUsageReport(usageMetrics{}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	text, _ := webhook.OnlyMessage(t)["text"].(string)
	if !strings.Contains(text, "Storage: 0.00 GB / 10 GB (0.00%)") ||
		!strings.Contains(text, "Class A: 0 / 1,000,000") {
		t.Errorf("unexpected report:\n%s", text)
	}
}

func TestSendUsageReportOverTheLimit(t *testing.T) {
	testutil.CaptureLog(t)
	webhook := useTestWebhook(t)

	if err := sendUsageReport(usageMetrics{ClassARequests: 1_500_000, StorageBytes: 12 * BYTES_IN_GB}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	text, _ := webhook.OnlyMessage(t)["text"].(string)
	if !strings.Contains(text, "12.00 GB / 10 GB (120.00%)") ||
		!strings.Contains(text, "1,500,000 / 1,000,000 (150.00%)") {
		t.Errorf("expected the usage over the limit, got:\n%s", text)
	}
}

func TestSendUsageReportReturnsTheMattermostError(t *testing.T) {
	testutil.CaptureLog(t)
	testCases := []struct {
		name string
		url  func(t *testing.T) string
	}{
		{name: "refused connection", url: func(*testing.T) string { return testutil.RefusedURL() }},
		{name: "error status", url: func(t *testing.T) string {
			t.Helper()
			webhook := testutil.NewFakeWebhook(t)
			webhook.Answer(http.StatusInternalServerError, "down")
			return webhook.URL()
		}},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			restoreConfig(t)
			MATTERMOST_WEBHOOK_URL = testCase.url(t)

			if err := sendUsageReport(usageMetrics{}); err == nil {
				t.Fatal("expected the delivery error")
			}
		})
	}
}

func TestHandlerRejectsOtherMethods(t *testing.T) {
	for _, method := range []string{http.MethodGet, http.MethodPut, http.MethodDelete} {
		recorder := check(method)

		if recorder.Code != http.StatusMethodNotAllowed {
			t.Errorf("%s: status = %d, want %d", method, recorder.Code, http.StatusMethodNotAllowed)
		}
		if body := strings.TrimSpace(recorder.Body.String()); body != "Only POST method is allowed" {
			t.Errorf("%s: body = %q", method, body)
		}
	}
}

func TestHandlerReportsTheUsage(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	webhook := useTestWebhook(t)
	fake.answerOperations(ok(operationsBody([]operation{{"PutObject", 2_000}, {"GetObject", 30_000}})))
	fake.answerStorage(ok(storageBody(point{"pnls-charts", "2026-11-27T10:00:00Z", BYTES_IN_GB, 0})))

	recorder := check(http.MethodPost)

	if recorder.Code != http.StatusOK ||
		recorder.Body.String() != "Cloudflare usage check sent to Mattermost info channel." {
		t.Fatalf("got %d %q", recorder.Code, recorder.Body.String())
	}
	text, _ := webhook.OnlyMessage(t)["text"].(string)
	for _, want := range []string{"1.00 GB / 10 GB (10.00%)", "Class A: 2,000 / 1,000,000", "Class B: 30,000 / 10,000,000"} {
		if !strings.Contains(text, want) {
			t.Errorf("expected %q in the report, got:\n%s", want, text)
		}
	}
	// The month is read in Paris time, from the 1st until now.
	start, _ := fake.received()[0].request.Variables["datetimeStart"].(string)
	if !strings.HasSuffix(start, "T22:00:00Z") && !strings.HasSuffix(start, "T23:00:00Z") {
		t.Errorf("datetimeStart = %q, want midnight in Paris", start)
	}
}

func TestHandlerWhenCloudflareFails(t *testing.T) {
	logs := testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	webhook := useTestWebhook(t)
	fake.answerOperations(failure(http.StatusUnauthorized, `{"errors":[{"message":"invalid token"}]}`))

	recorder := check(http.MethodPost)

	if recorder.Code != http.StatusInternalServerError ||
		strings.TrimSpace(recorder.Body.String()) != "Failed to fetch Cloudflare R2 metrics" {
		t.Fatalf("got %d %q", recorder.Code, recorder.Body.String())
	}
	if len(webhook.Messages()) != 0 {
		t.Error("expected no report")
	}
	if !strings.Contains(
		logs.String(),
		"Failed to fetch Cloudflare R2 metrics: cloudflare graphql returned status 401",
	) {
		t.Errorf("expected the error in the log, got:\n%s", logs.String())
	}
}

func TestHandlerWhenMattermostFails(t *testing.T) {
	logs := testutil.CaptureLog(t)
	useFakeCloudflare(t)
	webhook := useTestWebhook(t)
	webhook.Answer(http.StatusInternalServerError, "down")

	recorder := check(http.MethodPost)

	if recorder.Code != http.StatusBadGateway ||
		strings.TrimSpace(recorder.Body.String()) != "Failed to send Cloudflare usage report to Mattermost" {
		t.Fatalf("got %d %q", recorder.Code, recorder.Body.String())
	}
	if !strings.Contains(logs.String(), "Failed to send Cloudflare usage report to Mattermost") {
		t.Errorf("expected the error in the log, got:\n%s", logs.String())
	}
}

func TestHandlerFailuresAreReportedToSentry(t *testing.T) {
	testutil.CaptureLog(t)
	sentry := testutil.NewFakeSentry(t)
	logging.InitSentry(sentry.DSN(), SERVICE_NAME)
	t.Cleanup(func() { logging.InitSentry("", "") })
	fake := useFakeCloudflare(t)
	useTestWebhook(t)
	fake.answerOperations(failure(http.StatusUnauthorized, "invalid token"))

	if recorder := check(http.MethodPost); recorder.Code != http.StatusInternalServerError {
		t.Fatalf("expected the check to fail, got %d", recorder.Code)
	}

	reason := "a failed check is only logged, so an expired token or a Cloudflare outage is never reported."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, 2*time.Second); len(events) == 0 {
			t.Error("expected the failure in Sentry")
		}
	})
}

func freePort(t *testing.T) string {
	t.Helper()

	listener, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatalf("failed to find a free port: %v", err)
	}
	defer listener.Close()
	return strconv.Itoa(listener.Addr().(*net.TCPAddr).Port)
}

// serviceEnv is a .env file for main, with the values replacing the defaults.
func serviceEnv(t *testing.T, values map[string]string) string {
	t.Helper()

	return writeEnvFile(t, withValues(map[string]string{
		"MATTERMOST_WEBHOOK_URL":            "http://localhost:1/hooks/unused",
		"HTTP_PORT":                         freePort(t),
		"CHECK_ENDPOINT_PATH":               "/check",
		"CLOUDFLARE_API_TOKEN":              "token",
		"CLOUDFLARE_ACCOUNT_ID":             "0123abcd",
		"CLOUDFLARE_GRAPHQL_ENDPOINT":       "http://localhost:1/graphql",
		"CLOUDFLARE_GRAPHQL_RETRY_ATTEMPTS": "1",
	}, values))
}

// checkURLEnv passes the URL of the check to the child process.
const checkURLEnv = "CLIMNOT_TEST_CHECK_URL"

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

	fake := newFakeCloudflare(t)
	webhook := testutil.NewFakeWebhook(t)
	port := freePort(t)
	// The path is written without its leading slash, as normalizePath adds it.
	envDir := serviceEnv(t, map[string]string{
		"MATTERMOST_WEBHOOK_URL":      webhook.URL(),
		"HTTP_PORT":                   port,
		"CHECK_ENDPOINT_PATH":         "r2/check",
		"CLOUDFLARE_GRAPHQL_ENDPOINT": fake.server.URL,
	})

	result := runMainInChild(t, envDir, "http://localhost:"+port+"/r2/check")

	if !strings.Contains(result.Stdout, "reply: 200 Cloudflare usage check sent to Mattermost info channel.") {
		t.Fatalf("expected the check to succeed, got:\n%s", result.Output())
	}
	if !strings.Contains(result.Output(), SERVICE_NAME+" listening on :"+port+"/r2/check") {
		t.Errorf("expected the start to be logged, got:\n%s", result.Output())
	}
	if calls := fake.received(); len(calls) != 2 || calls[0].authorization != "Bearer token" {
		t.Errorf("expected the two queries with the token, got %+v", calls)
	}
	if messages := webhook.Messages(); len(messages) != 1 {
		t.Errorf("reports sent = %d, want 1", len(messages))
	}
}

func TestMainWithInvalidConfigurationFatal(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	testCases := map[string]map[string]string{
		"missing CLOUDFLARE_API_TOKEN":  {"CLOUDFLARE_API_TOKEN": ""},
		"missing CLOUDFLARE_ACCOUNT_ID": {"CLOUDFLARE_ACCOUNT_ID": ""},
		"missing HTTP_PORT":             {"HTTP_PORT": ""},
		"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS (1) must be >=": {
			"CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS":     "2",
			"CLOUDFLARE_GRAPHQL_RETRY_MAX_DELAY_SECONDS": "1",
		},
	}

	for wantErr, values := range testCases {
		result := runMainInChild(t, serviceEnv(t, values), "")

		if result.ExitCode != 1 || !strings.Contains(result.Output(), "Fatal Error: Invalid configuration: "+wantErr) {
			t.Errorf("expected %q and exit code 1, got %d:\n%s", wantErr, result.ExitCode, result.Output())
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

	result := runMainInChild(t, serviceEnv(t, map[string]string{"HTTP_PORT": port}), "")

	if result.ExitCode != 1 ||
		!strings.Contains(result.Output(), "Fatal Error: HTTP server failed: listen tcp :"+port) {
		t.Fatalf("expected the failed listen to end the service, got exit code %d:\n%s",
			result.ExitCode, result.Output())
	}
}
