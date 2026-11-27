package main

import (
	"fmt"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// workDirEnv passes the folder the child process runs in.
const workDirEnv = "DB_BACKUP_TEST_WORK_DIR"

// testKey is a valid AES-256 key, as the 32 characters themselves.
const testKey = "12345678901234567890123456789012"

// configVariables are the variables config.Load reads, which the child process must not inherit from a developer's
// shell.
var configVariables = []string{
	"CONDUCTOR_SERVER_URL", "DB_BACKUP_WORKFLOW_NAME", "DB_BACKUP_WORKFLOW_VERSION", "DB_BACKUP_SCHEDULE_NAME",
	"DB_BACKUP_SCHEDULE_CRON", "DB_BACKUP_TIMEZONE", "DB_BACKUP_WORKER_COUNT", "DB_BACKUP_POLL_INTERVAL_MS",
	"DB_BACKUP_PG_DUMP_BIN", "DB_BACKUP_WORK_DIR", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
	"R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET_NAME", "R2_BUCKET_PUBLIC_URL", "R2_ENDPOINT",
	"CLOUDFLARE_ACCOUNT_ID", "DB_BACKUP_ENCRYPTION_KEY", "DB_BACKUP_UPLOAD_TIMEOUT_SECONDS", "SENTRY_DSN",
	"SERVICE_NAME",
}

// moduleRoot is the db_backup folder, where the worker runs and finds workflows/.
func moduleRoot(t *testing.T) string {
	t.Helper()

	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot find the test file")
	}
	return filepath.Join(filepath.Dir(file), "..", "..")
}

// childEnv is the environment of the child process: no configuration, apart from the values, run in dir.
func childEnv(dir string, values map[string]string) []string {
	env := []string{workDirEnv + "=" + dir}
	for _, name := range configVariables {
		env = append(env, name+"="+values[name])
	}
	return env
}

// validEnv is a configuration that passes validation, with Conductor at conductorURL.
func validEnv(conductorURL string) map[string]string {
	return map[string]string{
		"CONDUCTOR_SERVER_URL":       conductorURL,
		"R2_ACCESS_KEY":              "access",
		"R2_SECRET_KEY":              "secret",
		"R2_BUCKET_NAME":             "pnls-backups",
		"R2_BUCKET_PUBLIC_URL":       "https://pub-backups.r2.dev",
		"R2_ENDPOINT":                "http://localhost:9000",
		"DB_BACKUP_ENCRYPTION_KEY":   testKey,
		"DB_BACKUP_POLL_INTERVAL_MS": "50",
	}
}

// newFakeConductor answers every request of the worker with an empty success: definitions are registered, and polls
// find no task.
func newFakeConductor(t *testing.T) string {
	t.Helper()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("[]"))
	}))
	t.Cleanup(server.Close)
	return server.URL + "/api"
}

// syncBuffer collects the log of the child process, which the worker's goroutines also write to.
type syncBuffer struct {
	mu      sync.Mutex
	builder strings.Builder
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.builder.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.builder.String()
}

func TestMainExitsOnAConfigurationError(t *testing.T) {
	if testutil.InChild(t) {
		t.Chdir(os.Getenv(workDirEnv))
		main()
		return
	}

	result := testutil.RunInChild(t, childEnv(t.TempDir(), nil)...)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: configuration error: R2_ACCESS_KEY, R2_SECRET_KEY and "+
		"R2_BUCKET_NAME are required") {
		t.Fatalf("expected the configuration error, got:\n%s", result.Output())
	}
}

func TestMainExitsWhenTheDefinitionsCantBeRegistered(t *testing.T) {
	if testutil.InChild(t) {
		t.Chdir(os.Getenv(workDirEnv))
		main()
		return
	}

	result := testutil.RunInChild(t, childEnv(moduleRoot(t), validEnv(testutil.RefusedURL()+"/api"))...)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: registration error") {
		t.Fatalf("expected the registration error, got:\n%s", result.Output())
	}
}

func TestMainExitsWithoutTheDefinitionFiles(t *testing.T) {
	if testutil.InChild(t) {
		t.Chdir(os.Getenv(workDirEnv))
		main()
		return
	}

	result := testutil.RunInChild(t, childEnv(t.TempDir(), validEnv(newFakeConductor(t)))...)

	if result.ExitCode != 1 || !strings.Contains(result.Output(), "registration error: read task definitions") {
		t.Fatalf("expected the missing definitions, got exit code %d:\n%s", result.ExitCode, result.Output())
	}
}

func TestMainStartsTheWorkers(t *testing.T) {
	if testutil.InChild(t) {
		t.Chdir(os.Getenv(workDirEnv))
		logs := &syncBuffer{}
		log.SetOutput(logs)

		go main()

		// main waits for a signal, so the child ends once the workers are up.
		deadline := time.Now().Add(20 * time.Second)
		for !strings.Contains(logs.String(), "db_backup worker started") {
			if time.Now().After(deadline) {
				fmt.Fprintf(os.Stderr, "the worker didn't start:\n%s", logs.String())
				os.Exit(3)
			}
			time.Sleep(20 * time.Millisecond)
		}
		fmt.Fprint(os.Stderr, logs.String())
		os.Exit(0)
	}

	conductorURL := newFakeConductor(t)
	result := testutil.RunInChild(t, childEnv(moduleRoot(t), validEnv(conductorURL))...)

	if result.ExitCode != 0 {
		t.Fatalf("expected the worker to start, got exit code %d:\n%s", result.ExitCode, result.Output())
	}
	want := "db_backup worker started. tasks=[pg_dump_task,encryption_task,compress_task,upload_to_r2_task," +
		"cleanup_local_files_task] conductor=" + conductorURL
	if !strings.Contains(result.Output(), want) {
		t.Fatalf("expected %q in the log, got:\n%s", want, result.Output())
	}
	if !strings.Contains(result.Output(), "sentry disabled: SENTRY_DSN is empty") {
		t.Errorf("expected Sentry to be off without a DSN, got:\n%s", result.Output())
	}
}

func TestInitSentryNamesTheWorker(t *testing.T) {
	if testutil.InChild(t) {
		initSentry(os.Getenv(testutil.SentryDSNEnv), "  ")
		logging.Fatal("backup failed")
		return
	}
	sentry := testutil.NewFakeSentry(t)

	result := testutil.RunInChild(t, testutil.SentryDSNEnv+"="+sentry.DSN())

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	events := sentry.WaitForEvents(1, 5*time.Second)
	if len(events) != 1 || events[0].Message != "backup failed" || events[0].ServerName != "db_backup_worker" {
		t.Fatalf("expected the event from db_backup_worker, got %+v", events)
	}
}

func TestConfigurationErrorsFromTheEnvFileReachSentry(t *testing.T) {
	if testutil.InChild(t) {
		// childEnv sets every variable, and godotenv never replaces one that is set, even when it's empty. The DSN
		// must come from the .env file, so it is the one variable left unset.
		if err := os.Unsetenv("SENTRY_DSN"); err != nil {
			t.Fatalf("failed to unset SENTRY_DSN: %v", err)
		}
		t.Chdir(os.Getenv(workDirEnv))
		main()
		return
	}
	sentry := testutil.NewFakeSentry(t)
	dir := t.TempDir()
	// The service is configured with a .env file, which has the DSN but misses the R2 keys.
	if err := os.WriteFile(filepath.Join(dir, ".env"), []byte("SENTRY_DSN="+sentry.DSN()+"\n"), 0o600); err != nil {
		t.Fatalf("failed to write the .env file: %v", err)
	}

	result := testutil.RunInChild(t, childEnv(dir, nil)...)

	if result.ExitCode != 1 || !strings.Contains(result.Output(), "configuration error") {
		t.Fatalf("expected the configuration error, got exit code %d:\n%s", result.ExitCode, result.Output())
	}
	reason := "main starts Sentry from the environment before config.Load reads .env, so with a .env file " +
		"Sentry stays off and the configuration error isn't reported."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, 2*time.Second); len(events) == 0 {
			t.Error("expected the configuration error in Sentry")
		}
	})
}
