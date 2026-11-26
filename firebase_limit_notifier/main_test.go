package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"maps"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func TestCheckFirebaseUsageHandlerRejectsNonPost(t *testing.T) {
	methods := []string{http.MethodGet, http.MethodHead, http.MethodPut, http.MethodDelete}

	for _, method := range methods {
		t.Run(method, func(t *testing.T) {
			checkRuns := 0
			handler := newCheckFirebaseUsageHandler(func() error {
				checkRuns++
				return nil
			})

			recorder := httptest.NewRecorder()
			handler(recorder, httptest.NewRequest(method, CHECK_PATH, http.NoBody))

			if recorder.Code != http.StatusMethodNotAllowed {
				t.Errorf("status = %d, want %d", recorder.Code, http.StatusMethodNotAllowed)
			}
			if checkRuns != 0 {
				t.Errorf("check ran %d times, want 0", checkRuns)
			}
		})
	}
}

func TestCheckFirebaseUsageHandlerRunsCheckOnPost(t *testing.T) {
	checkRuns := 0
	handler := newCheckFirebaseUsageHandler(func() error {
		checkRuns++
		return nil
	})

	recorder := httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodPost, CHECK_PATH, http.NoBody))

	if recorder.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusOK)
	}
	if checkRuns != 1 {
		t.Errorf("check ran %d times, want 1", checkRuns)
	}
	if body := recorder.Body.String(); body != "Firebase usage check sent to Mattermost info channel." {
		t.Errorf("unexpected body %q", body)
	}
}

func TestCheckFirebaseUsageHandlerReportsFailedCheck(t *testing.T) {
	handler := newCheckFirebaseUsageHandler(func() error {
		return errors.New("failed to send message to Mattermost: connection refused")
	})

	recorder := httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodPost, CHECK_PATH, http.NoBody))

	if recorder.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
	if body := strings.TrimSpace(recorder.Body.String()); body != "Failed to send Firebase usage report to Mattermost" {
		t.Errorf("unexpected body %q", body)
	}

	// The handler must keep serving requests after a failed check
	recorder = httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodPost, CHECK_PATH, http.NoBody))
	if recorder.Code != http.StatusBadGateway {
		t.Errorf("status after a second failed check = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
}

func TestCheckFirebaseUsageHandlerFailureIsReportedToSentry(t *testing.T) {
	sentry := testutil.NewFakeSentry(t)
	logging.InitSentry(sentry.DSN(), SERVICE_NAME)
	t.Cleanup(func() { logging.InitSentry("", SERVICE_NAME) })
	handler := newCheckFirebaseUsageHandler(func() error { return errors.New("connection refused") })

	handler(httptest.NewRecorder(), httptest.NewRequest(http.MethodPost, CHECK_PATH, http.NoBody))

	testutil.ExpectFailure(t, "A failed check is only logged, not sent to Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) == 0 {
			t.Error("expected the failure in Sentry, got no event")
		}
	})
}

// monthNodeNames are the nodes checkUsage reads: one per device and day, from the 1st of the month to today.
func monthNodeNames() []string {
	today := common.GetTimeNow(TIMEZONE)
	var names []string
	for _, device := range Devices {
		for day := 1; day <= today.Day(); day++ {
			names = append(names, fmt.Sprintf("%s-%04d-%02d-%02d", device, today.Year(), today.Month(), day))
		}
	}
	return names
}

// lastMonthNodeName is the node of the last day of last month, for the first device.
func lastMonthNodeName() string {
	today := common.GetTimeNow(TIMEZONE)
	lastDay := time.Date(today.Year(), today.Month(), 1, 12, 0, 0, 0, today.Location()).AddDate(0, 0, -1)
	return fmt.Sprintf("%s-%04d-%02d-%02d", Devices[0], lastDay.Year(), lastDay.Month(), lastDay.Day())
}

// collectorNode is what a collector writes for one day.
func collectorNode(index int) map[string]any {
	return map[string]any{
		"-Nx" + strconv.Itoa(index): map[string]any{
			"ssid":      "PNLS-" + strconv.Itoa(index),
			"bssid":     "aa:bb:cc:dd:ee:" + fmt.Sprintf("%02x", index%256),
			"rssi":      -40 - index%50,
			"timestamp": "2026-06-14 12:00:00",
		},
	}
}

// usageOf is the size checkUsage reports for the nodes, in MB. A node that doesn't exist counts as null.
func usageOf(t *testing.T, nodes map[string]any, names ...string) float64 {
	t.Helper()

	total := 0
	for _, name := range names {
		encoded, err := json.Marshal(nodes[name])
		if err != nil {
			t.Fatalf("failed to encode %s: %v", name, err)
		}
		total += len(encoded)
	}
	return float64(total) / BYTES_IN_MB
}

// newUsageDatabase is a fake database with a node for every other day of the month, and /stats.
func newUsageDatabase(t *testing.T) (*testutil.FakeRealtimeDatabase, map[string]any) {
	t.Helper()

	nodes := map[string]any{"stats": map[string]any{"devices": 3, "networks": 1520}}
	for index, name := range monthNodeNames() {
		if index%2 == 0 {
			nodes[name] = collectorNode(index)
		}
	}
	return testutil.NewFakeRealtimeDatabase(t, nodes), nodes
}

func TestCheckUsageAddsUpTheMonthAndStats(t *testing.T) {
	database, nodes := newUsageDatabase(t)
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(), database.DatabaseURL())

	usage := checkUsage(context.Background(), client)

	want := usageOf(t, nodes, append(monthNodeNames(), "stats")...)
	if usage != want {
		t.Fatalf("usage = %v MB, want %v MB", usage, want)
	}
}

func TestCheckUsageReadsEachDayOfEachDevice(t *testing.T) {
	database, _ := newUsageDatabase(t)
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(), database.DatabaseURL())

	checkUsage(context.Background(), client)

	want := append(monthNodeNames(), "stats")
	if got := database.Reads(); !slices.Equal(got, want) {
		t.Fatalf("read the nodes:\n%v\nwant:\n%v", got, want)
	}
}

func TestCheckUsageSkipsANodeThatFails(t *testing.T) {
	database, nodes := newUsageDatabase(t)
	failing := monthNodeNames()[0]
	database.FailReads(http.StatusInternalServerError, failing)
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(), database.DatabaseURL())
	logs := testutil.CaptureLog(t)

	usage := checkUsage(context.Background(), client)

	want := usageOf(t, nodes, append(monthNodeNames()[1:], "stats")...)
	if usage != want {
		t.Errorf("usage = %v MB, want %v MB without the failing node", usage, want)
	}
	if !strings.Contains(logs.String(), "Error fetching node "+failing) {
		t.Errorf("expected the failed read to be logged, got:\n%s", logs.String())
	}
}

func TestCheckUsageWithoutStats(t *testing.T) {
	database, nodes := newUsageDatabase(t)
	database.FailReads(http.StatusInternalServerError, "stats")
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(), database.DatabaseURL())
	logs := testutil.CaptureLog(t)

	usage := checkUsage(context.Background(), client)

	if want := usageOf(t, nodes, monthNodeNames()...); usage != want {
		t.Errorf("usage = %v MB, want %v MB without /stats", usage, want)
	}
	if !strings.Contains(logs.String(), "Error fetching /stats node") {
		t.Errorf("expected the failed read to be logged, got:\n%s", logs.String())
	}
}

func TestCheckUsageCountsLastMonthsNodesStillStored(t *testing.T) {
	database, _ := newUsageDatabase(t)
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(), database.DatabaseURL())

	checkUsage(context.Background(), client)

	reason := "checkUsage only reads this month's nodes, so last month's nodes housekeeping hasn't deleted yet aren't counted."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if !slices.Contains(database.Reads(), lastMonthNodeName()) {
			t.Errorf("expected %s to be counted, read %v", lastMonthNodeName(), database.Reads())
		}
	})
}

// useWebhook points the reports at a fake Mattermost webhook until the test ends.
func useWebhook(t *testing.T) *testutil.FakeWebhook {
	t.Helper()

	restoreConfig(t)
	webhook := testutil.NewFakeWebhook(t)
	MATTERMOST_WEBHOOK_URL = webhook.URL()
	return webhook
}

func TestCreateUsageChartSendsTheUsage(t *testing.T) {
	webhook := useWebhook(t)
	useUnreachableR2(t)

	if err := createUsageChart(250); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	message := webhook.OnlyMessage(t)
	if want := "Current Firebase Realtime DB usage is 250.00 MB out of 1 GB (25.00%)."; message["text"] != want {
		t.Errorf("text = %q, want %q", message["text"], want)
	}
	if message["username"] != SERVICE_NAME {
		t.Errorf("username = %v, want %q", message["username"], SERVICE_NAME)
	}
}

func TestCreateUsageChartRoundsTheUsage(t *testing.T) {
	webhook := useWebhook(t)
	useUnreachableR2(t)

	if err := createUsageChart(0.123456); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if text := webhook.OnlyMessage(t)["text"]; text != "Current Firebase Realtime DB usage is 0.12 MB out of 1 GB (0.01%)." {
		t.Errorf("unexpected text %q", text)
	}
}

func TestCreateUsageChartWithoutR2SendsTheMessageWithoutChart(t *testing.T) {
	webhook := useWebhook(t)
	useUnreachableR2(t)
	logs := testutil.CaptureLog(t)

	if err := createUsageChart(250); err != nil {
		t.Fatalf("expected the message to be sent without the chart, got %v", err)
	}

	if attachments, ok := webhook.OnlyMessage(t)["attachments"]; ok {
		t.Errorf("expected no attachment without a chart link, got %v", attachments)
	}
	if !strings.Contains(logs.String(), "There was an error uploading the the chart image to R2") {
		t.Errorf("expected the failed upload to be logged, got:\n%s", logs.String())
	}
	testutil.ExpectFailure(t, "A failed upload is also logged as a created image.", func(t testutil.TB) {
		if strings.Contains(logs.String(), "Image with a public Cloudflare R2 bucket link was created") {
			t.Errorf("did not expect a created image after the failed upload, got:\n%s", logs.String())
		}
	})
}

func TestCreateUsageChartOverTheLimitDrawsTheChart(t *testing.T) {
	webhook := useWebhook(t)
	useUnreachableR2(t)
	logs := testutil.CaptureLog(t)

	if err := createUsageChart(1200); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if text := webhook.OnlyMessage(t)["text"]; !strings.Contains(text.(string), "1200.00 MB out of 1 GB (120.00%)") {
		t.Errorf("unexpected text %q", text)
	}
	reason := "Over the limit, the free part is negative and the chart can't be drawn."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if strings.Contains(logs.String(), "There was an error generating a pie chart") {
			t.Errorf("expected the chart to be drawn, got:\n%s", logs.String())
		}
	})
}

func TestCreateUsageChartReturnsTheMattermostError(t *testing.T) {
	webhook := useWebhook(t)
	webhook.Answer(http.StatusInternalServerError, "")
	useUnreachableR2(t)

	if err := createUsageChart(250); err == nil {
		t.Fatal("expected an error when Mattermost doesn't take the report")
	}
}

// checkURLEnv passes the URL of the check to the child process.
const checkURLEnv = "FBLIMNOT_TEST_CHECK_URL"

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

// writeServiceFiles writes the .env file, with the values replacing the defaults, and the Firebase credentials file
// main reads, and returns their folder.
func writeServiceFiles(t *testing.T, credentialsFile string, values map[string]string) string {
	t.Helper()

	env := maps.Clone(testEnv)
	env["SENTRY_DSN"] = ""
	env["HTTP_PORT"] = freePort(t)
	maps.Copy(env, values)
	dir := writeEnvFile(t, env)

	credentials, err := os.ReadFile(credentialsFile)
	if err != nil {
		t.Fatalf("failed to read the credentials: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, FIREBASE_CREDENTIALS_FILE), credentials, 0o600); err != nil {
		t.Fatalf("failed to write the credentials: %v", err)
	}
	return dir
}

// runMainInChild runs main in a child process, in the folder with the service's files. With a check URL, the child
// sends one check once the server is up and prints the reply; without one, it waits a few seconds for main to exit.
func runMainInChild(t *testing.T, dir, checkURL string) testutil.ChildResult {
	t.Helper()

	if !testutil.InChild(t) {
		// The SDK tries an unreachable R2 only once.
		return testutil.RunInChild(t, envDirEnv+"="+dir, checkURLEnv+"="+checkURL, "AWS_MAX_ATTEMPTS=1")
	}

	unsetConfigEnv(t)
	t.Chdir(os.Getenv(envDirEnv))
	go main()

	checkURL = os.Getenv(checkURLEnv)
	deadline := time.Now().Add(3 * time.Second)
	if checkURL != "" {
		deadline = time.Now().Add(30 * time.Second)
	}
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

	database, nodes := newUsageDatabase(t)
	webhook := testutil.NewFakeWebhook(t)
	port := freePort(t)
	dir := writeServiceFiles(t, database.CredentialsFile(), map[string]string{
		"MATTERMOST_WEBHOOK_URL": webhook.URL(),
		"FIREBASE_DATABASE_URL":  database.DatabaseURL(),
		"R2_ENDPOINT":            testutil.RefusedURL(),
		"HTTP_PORT":              port,
		"CHECK_ENDPOINT_PATH":    "usage",
	})

	result := runMainInChild(t, dir, "http://localhost:"+port+"/usage")

	if !strings.Contains(result.Stdout, "reply: 200 Firebase usage check sent to Mattermost info channel.") {
		t.Fatalf("expected the check to succeed, got:\n%s", result.Output())
	}
	usage := usageOf(t, nodes, append(monthNodeNames(), "stats")...)
	want := fmt.Sprintf("Current Firebase Realtime DB usage is %.2f MB out of 1 GB", usage)
	if text, _ := webhook.OnlyMessage(t)["text"].(string); !strings.HasPrefix(text, want) {
		t.Errorf("expected the report to start with %q, got %q", want, text)
	}
}

func TestMainReportsAFailedCheckWhenFirebaseIsDown(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	database, _ := newUsageDatabase(t)
	database.FailReads(http.StatusUnauthorized)
	webhook := testutil.NewFakeWebhook(t)
	port := freePort(t)
	dir := writeServiceFiles(t, database.CredentialsFile(), map[string]string{
		"MATTERMOST_WEBHOOK_URL": webhook.URL(),
		"FIREBASE_DATABASE_URL":  database.DatabaseURL(),
		"R2_ENDPOINT":            testutil.RefusedURL(),
		"HTTP_PORT":              port,
	})

	result := runMainInChild(t, dir, "http://localhost:"+port+"/check")

	reason := "When every Firebase read fails, the check reports 0.00 MB and answers 200."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if !strings.Contains(result.Stdout, "reply: 502") {
			t.Errorf("expected the check to fail, got:\n%s", result.Stdout)
		}
		if messages := webhook.Messages(); len(messages) != 0 {
			t.Errorf("expected no usage report, got %v", messages)
		}
	})
}

func TestMainWithoutPortFatal(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	database, _ := newUsageDatabase(t)
	dir := writeServiceFiles(t, database.CredentialsFile(), map[string]string{
		"FIREBASE_DATABASE_URL": database.DatabaseURL(),
		"HTTP_PORT":             "",
	})

	result := runMainInChild(t, dir, "")

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: Invalid configuration: missing HTTP_PORT") {
		t.Fatalf("expected the missing port to be logged, got:\n%s", result.Output())
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
	database, _ := newUsageDatabase(t)
	dir := writeServiceFiles(t, database.CredentialsFile(), map[string]string{
		"FIREBASE_DATABASE_URL": database.DatabaseURL(),
		"HTTP_PORT":             port,
	})

	result := runMainInChild(t, dir, "")

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: HTTP server failed: listen tcp :"+port) {
		t.Fatalf("expected the failed listen to be logged, got:\n%s", result.Output())
	}
}

func TestMainWithoutWebhookFatal(t *testing.T) {
	if testutil.InChild(t) {
		runMainInChild(t, "", "")
		return
	}

	database, _ := newUsageDatabase(t)
	dir := writeServiceFiles(t, database.CredentialsFile(), map[string]string{
		"FIREBASE_DATABASE_URL":  database.DatabaseURL(),
		"MATTERMOST_WEBHOOK_URL": "",
	})

	result := runMainInChild(t, dir, "")

	testutil.ExpectFailure(t, "A missing MATTERMOST_WEBHOOK_URL isn't caught at startup.", func(t testutil.TB) {
		if result.ExitCode != 1 || !strings.Contains(result.Output(), "MATTERMOST_WEBHOOK_URL") {
			t.Errorf(
				"expected main to exit naming the variable, got exit code %d:\n%s",
				result.ExitCode,
				result.Output(),
			)
		}
	})
}
