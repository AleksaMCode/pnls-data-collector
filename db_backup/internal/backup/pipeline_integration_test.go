//go:build integration

package backup

import (
	"bytes"
	"compress/gzip"
	"context"
	"db_backup/internal/conductor"
	"db_backup/internal/config"
	"errors"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	conductorclient "github.com/conductor-sdk/conductor-go/sdk/client"
	conductormodel "github.com/conductor-sdk/conductor-go/sdk/model"
	"github.com/conductor-sdk/conductor-go/sdk/settings"
	"github.com/conductor-sdk/conductor-go/sdk/worker"
	workflowexecutor "github.com/conductor-sdk/conductor-go/sdk/workflow/executor"
	tc "github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"

	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil/containers"
)

// conductorImage is the Conductor server the workflow runs on in the tests.
const conductorImage = "conductoross/conductor-standalone:3.15.0"

var (
	conductorOnce sync.Once
	conductorURL  string
	conductorErr  error
)

// startConductor returns the URL of the Conductor API shared by the tests of this binary, and starts it on first use.
// The tests run one after the other, so their workers never take each other's tasks.
func startConductor(t *testing.T) string {
	t.Helper()

	conductorOnce.Do(func() {
		ctx := context.Background()
		container, err := tc.Run(ctx, conductorImage,
			tc.WithExposedPorts("8080/tcp"),
			tc.WithWaitStrategy(wait.ForHTTP("/health").WithPort("8080/tcp").WithStartupTimeout(2*time.Minute)),
		)
		if err != nil {
			conductorErr = err
			return
		}
		endpoint, err := container.PortEndpoint(ctx, "8080/tcp", "http")
		conductorURL, conductorErr = endpoint+"/api", err
	})
	if conductorErr != nil {
		t.Fatalf("failed to start Conductor: %v", conductorErr)
	}
	return conductorURL
}

// requirePgDump fails in CI, and skips elsewhere, without a local pg_dump. The worker writes the dump to its own
// disk, so pg_dump has to run on this machine, not in the Postgres container.
func requirePgDump(t *testing.T) {
	t.Helper()

	if _, err := exec.LookPath("pg_dump"); err != nil {
		if os.Getenv("CI") != "" {
			t.Fatalf("pg_dump is required for the integration tests in CI: %v", err)
		}
		t.Skipf("pg_dump is not installed, skipping the integration test: %v", err)
	}
}

// moduleRootPath is the db_backup folder, where the worker runs and finds workflows/.
func moduleRootPath(t *testing.T) string {
	t.Helper()

	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot resolve caller path")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(filename), "..", ".."))
}

// backupEnvironment is a seeded database, a bucket and Conductor, with the worker's config for them.
type backupEnvironment struct {
	cfg  config.Config
	silo *containers.Silo
}

func newBackupEnvironment(t *testing.T) *backupEnvironment {
	t.Helper()

	// Docker comes first: it skips the test when Docker isn't available, and fails it in CI.
	silo := containers.StartSilo(t)
	postgres := containers.StartPostgres(t)
	requirePgDump(t)

	database := postgres.CreateDatabase(t, "db_backup")
	seed, err := os.ReadFile(filepath.Join(moduleRootPath(t), "testdata", "db_backup_seed.sql"))
	if err != nil {
		t.Fatalf("failed to read the seed: %v", err)
	}
	postgres.Exec(t, database, string(seed))

	cfg := config.Config{
		ConductorServerURL:  startConductor(t),
		WorkflowName:        "db_backup_workflow",
		WorkflowVersion:     1,
		ScheduleName:        "db_backup_daily_2300_paris",
		ScheduleCron:        "0 0 23 * * ?",
		Timezone:            "Europe/Paris",
		WorkerCount:         2,
		PollInterval:        100 * time.Millisecond,
		PgDumpBin:           "pg_dump",
		WorkDir:             t.TempDir(),
		DBHost:              postgres.Host,
		DBPort:              postgres.Port,
		DBUser:              containers.PostgresUser,
		DBPassword:          containers.PostgresPassword,
		DBName:              database,
		R2AccessKey:         containers.SiloAccessKey,
		R2SecretKey:         containers.SiloSecretKey,
		R2BucketName:        silo.CreateBucket(t, "db-backup-it"),
		R2BucketPublicURL:   "https://pub-backups.r2.dev",
		R2Endpoint:          silo.Endpoint,
		CloudflareAccountID: "local",
		EncryptionKeyRaw:    testKey,
		UploadTimeout:       30 * time.Second,
	}
	if err := cfg.Validate(); err != nil {
		t.Fatalf("config validation failed: %v", err)
	}
	return &backupEnvironment{cfg: cfg, silo: silo}
}

// runWorkflow registers the definitions, runs the worker with cfg until the workflow ends, and returns the workflow.
func runWorkflow(t *testing.T, cfg config.Config) *conductormodel.Workflow {
	t.Helper()

	ctx := t.Context()
	t.Chdir(moduleRootPath(t))
	apiClient := conductorclient.NewAPIClient(nil, settings.NewHttpSettings(cfg.ConductorServerURL))
	if err := conductor.RegisterAll(ctx, cfg, apiClient); err != nil {
		t.Fatalf("failed to register the definitions: %v", err)
	}

	store, err := objectstore.New(ctx, cfg.ObjectStore())
	if err != nil {
		t.Fatalf("failed to make the store: %v", err)
	}
	pipeline := NewPipeline(cfg, store)

	// The same handlers as in cmd/worker/main.go.
	taskRunner := worker.NewTaskRunnerWithApiClient(apiClient)
	handlers := map[string]func(*conductormodel.Task) (any, error){
		TaskPgDumpName:   func(task *conductormodel.Task) (any, error) { return pipeline.RunPgDumpTask(ctx, task) },
		TaskEncryptName:  func(task *conductormodel.Task) (any, error) { return pipeline.RunEncryptTask(ctx, task) },
		TaskCompressName: func(task *conductormodel.Task) (any, error) { return pipeline.RunCompressTask(ctx, task) },
		TaskUploadName: func(task *conductormodel.Task) (any, error) {
			output, err := pipeline.RunUploadTask(ctx, task)
			if err != nil {
				return nil, err
			}
			return output, nil
		},
		TaskCleanupName: func(task *conductormodel.Task) (any, error) { return pipeline.RunCleanupTask(ctx, task) },
	}
	for name, handler := range handlers {
		if err := taskRunner.StartWorker(name, handler, cfg.WorkerCount, cfg.PollInterval); err != nil {
			t.Fatalf("failed to start the %s worker: %v", name, err)
		}
	}
	defer func() {
		for name := range handlers {
			taskRunner.Shutdown(name)
		}
		taskRunner.WaitWorkers()
	}()

	executor := workflowexecutor.NewWorkflowExecutor(apiClient)
	workflowID, err := executor.StartWorkflow(&conductormodel.StartWorkflowRequest{
		Name:    cfg.WorkflowName,
		Version: cfg.WorkflowVersion,
		Input:   map[string]any{},
	})
	if err != nil {
		t.Fatalf("failed to start the workflow: %v", err)
	}
	monitor, err := executor.MonitorExecution(workflowID)
	if err != nil {
		t.Fatalf("failed to monitor the workflow: %v", err)
	}
	if _, err := workflowexecutor.WaitForWorkflowCompletionUntilTimeout(monitor, 2*time.Minute); err != nil {
		t.Fatalf("the workflow didn't end: %v", err)
	}
	// The monitor's workflow has no tasks, so read it again with them.
	workflow, err := executor.GetWorkflow(workflowID, true)
	if err != nil {
		t.Fatalf("failed to read the workflow: %v", err)
	}
	return workflow
}

func TestWorkflowBacksUpTheDatabaseToTheBucket(t *testing.T) {
	testutil.CaptureLog(t)
	env := newBackupEnvironment(t)

	workflow := runWorkflow(t, env.cfg)

	if !workflow.IsCompleted() {
		t.Fatalf("the workflow ended as %s: %s", workflow.Status, workflow.ReasonForIncompletion)
	}
	objectKey, _ := workflow.Output["object_key"].(string)
	if !strings.HasPrefix(objectKey, "db-backup/") || !strings.HasSuffix(objectKey, ".sql.enc.gz") {
		t.Fatalf("unexpected object_key in the workflow output %#v", workflow.Output)
	}
	if objectPath := workflow.Output["object_path"]; objectPath != "https://pub-backups.r2.dev/"+objectKey {
		t.Errorf("object_path = %v", objectPath)
	}

	uploaded, contentType := env.silo.GetObject(t, env.cfg.R2BucketName, objectKey)
	if contentType != "application/gzip" {
		t.Errorf("content type = %q, want application/gzip", contentType)
	}
	reader, err := gzip.NewReader(bytes.NewReader(uploaded))
	if err != nil {
		t.Fatalf("the backup isn't a gzip file: %v", err)
	}
	encrypted, err := io.ReadAll(reader)
	if err != nil {
		t.Fatalf("failed to gunzip the backup: %v", err)
	}
	dump := string(decrypt(t, encrypted))
	if !strings.Contains(dump, "CREATE TABLE public.people") || !strings.Contains(dump, "Alice") {
		t.Fatalf("the backup doesn't have the seeded table and rows:\n%s", dump)
	}

	if entries, err := os.ReadDir(env.cfg.WorkDir); err != nil || len(entries) != 0 {
		t.Errorf("expected the cleanup to empty the work folder, got %v, %v", entries, err)
	}
}

func TestFailedWorkflowLeavesNoDumpBehind(t *testing.T) {
	testutil.CaptureLog(t)
	env := newBackupEnvironment(t)
	// The dump succeeds, and the encryption then fails for good, without a retry.
	cfg := env.cfg
	cfg.EncryptionKeyRaw = "too-short"

	workflow := runWorkflow(t, cfg)

	if keys := env.silo.ListKeys(t, cfg.R2BucketName); len(keys) != 0 {
		t.Errorf("expected nothing uploaded, got %v", keys)
	}
	if workflow.Status != conductormodel.FailedWorkflow {
		t.Fatalf("expected the workflow to fail, got %s", workflow.Status)
	}
	reason := "the handlers other than the upload's return their empty output with the error, and the SDK only " +
		"reports an error when the output is nil, so a failed encryption is COMPLETED, and the workflow only fails " +
		"at the upload, which finds no file."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		for _, task := range workflow.Tasks {
			if task.TaskDefName == TaskEncryptName && task.Status != conductormodel.FailedWithTerminalErrorTask {
				t.Errorf("the encryption ended as %s, want %s", task.Status, conductormodel.FailedWithTerminalErrorTask)
			}
		}
		if !strings.Contains(workflow.ReasonForIncompletion, "key must decode to 32 bytes") {
			t.Errorf("expected the key error as the reason, got %q", workflow.ReasonForIncompletion)
		}
	})

	dumpPath := filepath.Join(cfg.WorkDir, workflow.WorkflowId, "backup.sql")
	reason = "a failed workflow never runs the cleanup task, and has no failure workflow, so the unencrypted " +
		"dump stays on disk."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if _, err := os.Stat(dumpPath); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("expected no dump left at %s, got %v", dumpPath, err)
		}
	})
}
