package logging

import (
	"log"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/getsentry/sentry-go"

	"github.com/AleksaMCode/pnls-data-collector/util-go/internal/testsupport"
)

// logFileEnv passes the log file to the child process. The log file stays open until the process ends, so the tests
// that write to it run in a child process; Windows can't remove an open file when the test's folder is cleaned up.
const logFileEnv = "UTIL_GO_TEST_LOG_FILE"

func readLogFile(t *testing.T, path string) string {
	t.Helper()

	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read the log file: %v", err)
	}
	return string(content)
}

// captureLog sends the standard logger to a buffer until the test ends.
func captureLog(t *testing.T) *strings.Builder {
	t.Helper()

	var buffer strings.Builder
	original := log.Writer()
	log.SetOutput(&buffer)
	t.Cleanup(func() { log.SetOutput(original) })
	return &buffer
}

// useFakeSentry sets up Sentry for the test with a fake server, and turns Sentry off when the test ends.
func useFakeSentry(t *testing.T, serviceName string) *testsupport.FakeSentry {
	t.Helper()

	fake := testsupport.NewFakeSentry(t)
	InitSentry(fake.DSN(), serviceName)
	t.Cleanup(func() { _ = sentry.Init(sentry.ClientOptions{}) })
	return fake
}

func TestInitLoggingWritesToStdoutAndTheFile(t *testing.T) {
	if testsupport.InChild(t) {
		InitLogging(os.Getenv(logFileEnv))
		log.Print("Checking the collectors.")
		return
	}

	logFile := filepath.Join(t.TempDir(), "collector_status_notifier.log")
	result := testsupport.RunInChild(t, logFileEnv+"="+logFile)

	if !strings.Contains(result.Stdout, "Checking the collectors.") {
		t.Errorf("expected the record on stdout, got:\n%s", result.Stdout)
	}
	if strings.Contains(result.Stderr, "Checking the collectors.") {
		t.Errorf("did not expect the record on stderr, got:\n%s", result.Stderr)
	}
	if content := readLogFile(t, logFile); !strings.Contains(content, "Checking the collectors.") {
		t.Errorf("expected the record in the log file, got:\n%s", content)
	}
}

func TestInitLoggingCreatesTheLogFolder(t *testing.T) {
	if testsupport.InChild(t) {
		InitLogging(os.Getenv(logFileEnv))
		log.Print("Started.")
		return
	}

	logFile := filepath.Join(t.TempDir(), "logs", "notifier", "service.log")
	testsupport.RunInChild(t, logFileEnv+"="+logFile)

	if content := readLogFile(t, logFile); !strings.Contains(content, "Started.") {
		t.Fatalf("expected the record in the log file, got:\n%s", content)
	}
}

func TestInitLoggingAppendsToAnExistingFile(t *testing.T) {
	if testsupport.InChild(t) {
		InitLogging(os.Getenv(logFileEnv))
		log.Print("Second run.")
		return
	}

	logFile := filepath.Join(t.TempDir(), "service.log")
	if err := os.WriteFile(logFile, []byte("First run.\n"), 0o600); err != nil {
		t.Fatalf("failed to write the log file: %v", err)
	}
	testsupport.RunInChild(t, logFileEnv+"="+logFile)

	content := readLogFile(t, logFile)
	if !strings.HasPrefix(content, "First run.\n") || !strings.Contains(content, "Second run.") {
		t.Fatalf("expected the new record after the old one, got:\n%s", content)
	}
}

func TestInitSentryTagsEventsWithTheServiceName(t *testing.T) {
	fake := useFakeSentry(t, "Cloudflare limit notifier")

	sentry.CaptureMessage("R2 storage is at 80%.")
	sentry.Flush(2 * time.Second)

	events := fake.Events()
	if len(events) != 1 {
		t.Fatalf("expected one event, got %+v", events)
	}
	if events[0].Message != "R2 storage is at 80%." || events[0].ServerName != "Cloudflare limit notifier" {
		t.Fatalf("unexpected event: %+v", events[0])
	}
}

func TestInitSentryWithAnInvalidDSNIsLoggedAndCarriesOn(t *testing.T) {
	logs := captureLog(t)
	t.Cleanup(func() { _ = sentry.Init(sentry.ClientOptions{}) })

	InitSentry("not a dsn", "Firebase limit notifier")

	if !strings.Contains(logs.String(), "sentry init failed") {
		t.Fatalf("expected the failure to be logged, got:\n%s", logs.String())
	}
}

func TestInitSentryWithoutDSNTurnsSentryOff(t *testing.T) {
	fake := useFakeSentry(t, "Home Server limit notifier")
	logs := captureLog(t)

	InitSentry("", "Home Server limit notifier")
	sentry.CaptureMessage("not sent")
	sentry.Flush(time.Second)

	if logs.Len() != 0 {
		t.Fatalf("did not expect anything to be logged, got:\n%s", logs.String())
	}
	if events := fake.Events(); len(events) != 0 {
		t.Fatalf("did not expect an event to be sent, got %+v", events)
	}
}

func TestFatalLogsReportsToSentryAndExits(t *testing.T) {
	if testsupport.InChild(t) {
		InitObservability(os.Getenv(logFileEnv), os.Getenv(testsupport.SentryDSNEnv), "Firebase limit notifier")
		Fatal("Firebase usage could not be read.")
		log.Print("Still running.")
		return
	}

	fake := testsupport.NewFakeSentry(t)
	logFile := filepath.Join(t.TempDir(), "firebase_limit_notifier.log")
	result := testsupport.RunInChild(t, logFileEnv+"="+logFile, testsupport.SentryDSNEnv+"="+fake.DSN())

	if result.ExitCode != 1 {
		t.Errorf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	content := readLogFile(t, logFile)
	if !strings.Contains(content, "Fatal Error: Firebase usage could not be read.") {
		t.Errorf("expected the error in the log file, got:\n%s", content)
	}
	if strings.Contains(content, "Still running.") {
		t.Errorf("expected the process to stop at Fatal, got:\n%s", content)
	}

	events := fake.Events()
	if len(events) != 1 {
		t.Fatalf("expected one event in Sentry before the exit, got %+v", events)
	}
	want := testsupport.SentryEvent{
		Message:    "Firebase usage could not be read.",
		Level:      "fatal",
		ServerName: "Firebase limit notifier",
	}
	if events[0] != want {
		t.Fatalf("expected %+v, got %+v", want, events[0])
	}
}

func TestFatalBeforeSetupOnlyLogs(t *testing.T) {
	// As when the .env file can't be loaded: the services load it before they set up logging and Sentry.
	if testsupport.InChild(t) {
		Fatal("Error loading .env file")
		return
	}

	result := testsupport.RunInChild(t)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Stderr, "Fatal Error: Error loading .env file") {
		t.Fatalf("expected the error on stderr, got:\n%s", result.Output())
	}
}
