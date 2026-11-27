package backup

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"db_backup/internal/config"
	localmodel "db_backup/internal/model"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"

	conductormodel "github.com/conductor-sdk/conductor-go/sdk/model"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// The test binary stands in for pg_dump when fakePgDumpEnv is set: it records how it was called in the file named by
// fakePgDumpRecordEnv, then writes fakePgDumpContentEnv to the --file, or fails with fakePgDumpFailEnv as its output.
const (
	fakePgDumpEnv        = "DB_BACKUP_TEST_FAKE_PG_DUMP"
	fakePgDumpRecordEnv  = "DB_BACKUP_TEST_FAKE_PG_DUMP_RECORD"
	fakePgDumpContentEnv = "DB_BACKUP_TEST_FAKE_PG_DUMP_CONTENT"
	fakePgDumpFailEnv    = "DB_BACKUP_TEST_FAKE_PG_DUMP_FAIL"
)

// testKey is a valid AES-256 key, as the 32 characters themselves.
const testKey = "12345678901234567890123456789012"

func TestMain(m *testing.M) {
	if os.Getenv(fakePgDumpEnv) != "" {
		os.Exit(fakePgDump())
	}
	os.Exit(m.Run())
}

// pgDumpCall is how the fake pg_dump was called.
type pgDumpCall struct {
	Args     []string `json:"args"`
	Password string   `json:"password"`
}

func fakePgDump() int {
	args := os.Args[1:]
	record, _ := json.Marshal(pgDumpCall{Args: args, Password: os.Getenv("PGPASSWORD")})
	if err := os.WriteFile(os.Getenv(fakePgDumpRecordEnv), record, 0o600); err != nil {
		fmt.Fprintf(os.Stderr, "fake pg_dump: %v\n", err)
		return 2
	}

	if message := os.Getenv(fakePgDumpFailEnv); message != "" {
		fmt.Fprintln(os.Stderr, message)
		return 1
	}
	index := slices.Index(args, "--file")
	if index < 0 || index+1 >= len(args) {
		fmt.Fprintln(os.Stderr, "fake pg_dump: no --file")
		return 2
	}
	if err := os.WriteFile(args[index+1], []byte(os.Getenv(fakePgDumpContentEnv)), 0o600); err != nil {
		fmt.Fprintf(os.Stderr, "fake pg_dump: %v\n", err)
		return 2
	}
	return 0
}

// fakePgDumpRun is a fake pg_dump set up for a test.
type fakePgDumpRun struct {
	recordPath string
}

// useFakePgDump makes the config run the fake pg_dump, which dumps content, until the test ends.
func useFakePgDump(t *testing.T, cfg *config.Config, content string) *fakePgDumpRun {
	t.Helper()

	run := &fakePgDumpRun{recordPath: filepath.Join(t.TempDir(), "pg_dump.json")}
	t.Setenv(fakePgDumpEnv, "1")
	t.Setenv(fakePgDumpRecordEnv, run.recordPath)
	t.Setenv(fakePgDumpContentEnv, content)
	t.Setenv(fakePgDumpFailEnv, "")
	cfg.PgDumpBin = os.Args[0]
	return run
}

// call returns how the fake pg_dump was called, and fails the test if it wasn't.
func (r *fakePgDumpRun) call(t *testing.T) pgDumpCall {
	t.Helper()

	data, err := os.ReadFile(r.recordPath)
	if err != nil {
		t.Fatalf("pg_dump wasn't run: %v", err)
	}
	var call pgDumpCall
	if err := json.Unmarshal(data, &call); err != nil {
		t.Fatalf("failed to read the pg_dump call: %v", err)
	}
	return call
}

func (r *fakePgDumpRun) wasRun() bool {
	_, err := os.Stat(r.recordPath)
	return err == nil
}

// fakeUploader records the uploads and answers them with its link or its error.
type fakeUploader struct {
	mu      sync.Mutex
	link    string
	err     error
	uploads []recordedUpload
}

type recordedUpload struct {
	key, path   string
	opts        objectstore.UploadOptions
	deadline    time.Time
	hasDeadline bool
}

func (f *fakeUploader) Upload(context.Context, string, io.Reader, objectstore.UploadOptions) (string, error) {
	return "", errors.New("the pipeline uploads files, not readers")
}

func (f *fakeUploader) UploadFile(
	ctx context.Context,
	key, path string,
	opts objectstore.UploadOptions,
) (string, error) {
	deadline, hasDeadline := ctx.Deadline()
	f.mu.Lock()
	defer f.mu.Unlock()
	f.uploads = append(f.uploads, recordedUpload{
		key: key, path: path, opts: opts, deadline: deadline, hasDeadline: hasDeadline,
	})
	return f.link, f.err
}

func (f *fakeUploader) calls() []recordedUpload {
	f.mu.Lock()
	defer f.mu.Unlock()
	return slices.Clone(f.uploads)
}

// testConfig is the config of the tests, with a work folder that is removed when the test ends.
func testConfig(t *testing.T) config.Config {
	t.Helper()

	return config.Config{
		Timezone:         "Europe/Paris",
		WorkDir:          t.TempDir(),
		PgDumpBin:        "pg_dump",
		DBHost:           "postgres",
		DBPort:           "5432",
		DBUser:           "backup",
		DBPassword:       "s3cret",
		DBName:           "app",
		EncryptionKeyRaw: testKey,
		UploadTimeout:    30 * time.Second,
	}
}

func task(taskID, workflowID string, input map[string]any) *conductormodel.Task {
	return &conductormodel.Task{TaskId: taskID, WorkflowInstanceId: workflowID, InputData: input}
}

// requireNonRetryable fails the test unless err tells Conductor not to retry the task.
func requireNonRetryable(t testutil.TB, err error, want string) {
	t.Helper()

	if err == nil {
		t.Fatalf("expected an error with %q", want)
	}
	if _, ok := errors.AsType[*conductormodel.NonRetryableError](err); !ok {
		t.Errorf("expected a non-retryable error, got %T: %v", err, err)
	}
	if !strings.Contains(err.Error(), want) {
		t.Errorf("expected %q in the error, got %v", want, err)
	}
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()

	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("failed to write %s: %v", path, err)
	}
}

func readFile(t testutil.TB, path string) []byte {
	t.Helper()

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read %s: %v", path, err)
	}
	return data
}

func decrypt(t testutil.TB, encrypted []byte) []byte {
	t.Helper()

	block, err := aes.NewCipher([]byte(testKey))
	if err != nil {
		t.Fatalf("failed to make the cipher: %v", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		t.Fatalf("failed to make GCM: %v", err)
	}
	if len(encrypted) < gcm.NonceSize() {
		t.Fatalf("the encrypted file is too short: %d bytes", len(encrypted))
	}
	plaintext, err := gcm.Open(nil, encrypted[:gcm.NonceSize()], encrypted[gcm.NonceSize():], nil)
	if err != nil {
		t.Fatalf("failed to decrypt: %v", err)
	}
	return plaintext
}

func gunzip(t *testing.T, path string) []byte {
	t.Helper()

	reader, err := gzip.NewReader(bytes.NewReader(readFile(t, path)))
	if err != nil {
		t.Fatalf("failed to open the gzip file: %v", err)
	}
	defer reader.Close()
	content, err := io.ReadAll(reader)
	if err != nil {
		t.Fatalf("failed to gunzip: %v", err)
	}
	return content
}

func requirePrivate(t *testing.T, path string, want os.FileMode) {
	t.Helper()

	if runtime.GOOS == "windows" {
		return // Windows has no Unix permissions.
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("failed to stat %s: %v", path, err)
	}
	if info.Mode().Perm() != want {
		t.Errorf("%s has the permissions %v, want %v", path, info.Mode().Perm(), want)
	}
}

func TestRunPgDumpTaskDumpsTheDatabase(t *testing.T) {
	cfg := testConfig(t)
	pgDump := useFakePgDump(t, &cfg, "CREATE TABLE people;")

	output, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task(" task-1 ", " workflow-1 ", nil))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	baseDir := filepath.Join(cfg.WorkDir, "workflow-1")
	dumpPath := filepath.Join(baseDir, "backup.sql")
	if output.WorkflowID != "workflow-1" || output.BaseDir != baseDir || output.DumpPath != dumpPath ||
		output.DumpFileName != "backup.sql" {
		t.Errorf("unexpected output %+v", output)
	}
	if content := readFile(t, dumpPath); string(content) != "CREATE TABLE people;" {
		t.Errorf("dump = %q", content)
	}
	requirePrivate(t, baseDir, 0o700)

	call := pgDump.call(t)
	wantArgs := []string{
		"--file", dumpPath, "--format=plain", "--no-owner", "--no-privileges",
		"--host", "postgres", "--port", "5432", "--username", "backup", "--dbname", "app",
	}
	if !slices.Equal(call.Args, wantArgs) {
		t.Errorf("pg_dump arguments =\n%q\nwant\n%q", call.Args, wantArgs)
	}
	if call.Password != "s3cret" {
		t.Errorf("PGPASSWORD = %q, want the database password", call.Password)
	}
}

func TestRunPgDumpTaskTimestampIsInTheConfiguredTimezone(t *testing.T) {
	cfg := testConfig(t)
	useFakePgDump(t, &cfg, "")
	paris, err := time.LoadLocation("Europe/Paris")
	if err != nil {
		t.Fatalf("failed to load Europe/Paris: %v", err)
	}

	before := time.Now().Unix()
	output, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task("task-1", "workflow-1", nil))
	after := time.Now().Unix()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if output.TimestampUnix < before || output.TimestampUnix > after {
		t.Errorf("TimestampUnix = %d, want between %d and %d", output.TimestampUnix, before, after)
	}
	moment := time.Unix(output.TimestampUnix, 0)
	if want := moment.In(paris).Format("20060102T150405"); output.Timestamp != want {
		t.Errorf("Timestamp = %q, want %q, the Paris time", output.Timestamp, want)
	}
	// Paris is always ahead of UTC, so the timestamp shows which zone was used.
	if output.Timestamp == moment.UTC().Format("20060102T150405") {
		t.Errorf("Timestamp %q is in UTC", output.Timestamp)
	}
}

func TestRunPgDumpTaskRequiresTheIDs(t *testing.T) {
	testCases := []struct {
		name, taskID, workflowID string
	}{
		{name: "no task id", workflowID: "workflow-1"},
		{name: "no workflow id", taskID: "task-1"},
		{name: "spaces only", taskID: "  ", workflowID: "\t"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			cfg := testConfig(t)
			pgDump := useFakePgDump(t, &cfg, "")

			_, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task(testCase.taskID, testCase.workflowID, nil))

			requireNonRetryable(t, err, "missing task id or workflow id")
			if pgDump.wasRun() {
				t.Error("expected pg_dump not to run")
			}
		})
	}
}

func TestRunPgDumpTaskInvalidTimezone(t *testing.T) {
	cfg := testConfig(t)
	cfg.Timezone = "Mars/Olympus_Mons"
	pgDump := useFakePgDump(t, &cfg, "")

	_, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task("task-1", "workflow-1", nil))

	requireNonRetryable(t, err, "invalid timezone")
	if pgDump.wasRun() {
		t.Error("expected pg_dump not to run")
	}
}

func TestRunPgDumpTaskReportsThePgDumpOutput(t *testing.T) {
	cfg := testConfig(t)
	useFakePgDump(t, &cfg, "")
	t.Setenv(fakePgDumpFailEnv, `pg_dump: error: connection to server failed: FATAL: password authentication failed`)

	_, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task("task-1", "workflow-1", nil))

	if err == nil || !strings.Contains(err.Error(), "pg_dump failed") ||
		!strings.Contains(err.Error(), "password authentication failed") {
		t.Fatalf("expected the pg_dump output in the error, got %v", err)
	}
	// A database that is down for a moment is worth another try.
	if _, ok := errors.AsType[*conductormodel.NonRetryableError](err); ok {
		t.Errorf("expected a retryable error, got %v", err)
	}
}

func TestRunPgDumpTaskWithoutPgDump(t *testing.T) {
	cfg := testConfig(t)
	cfg.PgDumpBin = filepath.Join(t.TempDir(), "missing-pg_dump")

	_, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task("task-1", "workflow-1", nil))

	if err == nil || !strings.Contains(err.Error(), "pg_dump failed") {
		t.Fatalf("expected the pg_dump error, got %v", err)
	}
}

func TestRunPgDumpTaskWhenTheWorkFolderCantBeCreated(t *testing.T) {
	cfg := testConfig(t)
	cfg.WorkDir = filepath.Join(t.TempDir(), "file")
	writeFile(t, cfg.WorkDir, "not a folder")
	pgDump := useFakePgDump(t, &cfg, "")

	if _, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task("task-1", "workflow-1", nil)); err == nil {
		t.Fatal("expected an error when the work folder is a file")
	}
	if pgDump.wasRun() {
		t.Error("expected pg_dump not to run")
	}
}

func TestRunPgDumpTaskStopsWithTheContext(t *testing.T) {
	cfg := testConfig(t)
	useFakePgDump(t, &cfg, "")
	ctx, cancel := context.WithCancel(t.Context())
	cancel()

	if _, err := NewPipeline(cfg, nil).RunPgDumpTask(ctx, task("task-1", "workflow-1", nil)); err == nil {
		t.Fatal("expected an error with a cancelled context")
	}
}

// dumpInput writes a dump into a new work folder and returns the encryption task's input for it.
func dumpInput(t *testing.T, content string) map[string]any {
	t.Helper()

	baseDir := t.TempDir()
	dumpPath := filepath.Join(baseDir, "backup.sql")
	writeFile(t, dumpPath, content)
	return map[string]any{
		"dump_path":      dumpPath,
		"base_dir":       baseDir,
		"timestamp":      "20261126T230000",
		"dump_file_name": "backup.sql",
	}
}

func TestRunEncryptTaskEncryptsTheDump(t *testing.T) {
	input := dumpInput(t, "INSERT INTO people VALUES ('Alice');")

	output, err := NewPipeline(testConfig(t), nil).RunEncryptTask(t.Context(), task("task-2", "workflow-1", input))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	encPath := filepath.Join(input["base_dir"].(string), "backup.sql.enc")
	want := encryptOutputFor(input, "workflow-1", encPath)
	if output != want {
		t.Errorf("output = %+v, want %+v", output, want)
	}
	encrypted := readFile(t, encPath)
	if bytes.Contains(encrypted, []byte("Alice")) {
		t.Error("the encrypted file contains the plain text")
	}
	if plaintext := decrypt(t, encrypted); string(plaintext) != "INSERT INTO people VALUES ('Alice');" {
		t.Errorf("decrypted = %q", plaintext)
	}
	requirePrivate(t, encPath, 0o600)
}

func TestRunEncryptTaskUsesANewNonceEachTime(t *testing.T) {
	pipeline := NewPipeline(testConfig(t), nil)
	input := dumpInput(t, "same dump")
	encPath := filepath.Join(input["base_dir"].(string), "backup.sql.enc")

	if _, err := pipeline.RunEncryptTask(t.Context(), task("task-2", "workflow-1", input)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	first := readFile(t, encPath)
	if _, err := pipeline.RunEncryptTask(t.Context(), task("task-2", "workflow-1", input)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	second := readFile(t, encPath)

	// Reusing a nonce with the same key breaks AES-GCM.
	if bytes.Equal(first[:12], second[:12]) {
		t.Fatal("expected a new nonce for each encryption")
	}
}

func TestRunEncryptTaskRequiresItsInput(t *testing.T) {
	for _, key := range []string{"dump_path", "base_dir", "timestamp", "dump_file_name"} {
		t.Run(key, func(t *testing.T) {
			input := dumpInput(t, "dump")
			delete(input, key)

			_, err := NewPipeline(testConfig(t), nil).RunEncryptTask(t.Context(), task("task-2", "workflow-1", input))

			requireNonRetryable(t, err, "missing required input key: "+key)
		})
	}
}

func TestRunEncryptTaskWithAnInvalidKey(t *testing.T) {
	cfg := testConfig(t)
	cfg.EncryptionKeyRaw = "short"

	_, err := NewPipeline(cfg, nil).RunEncryptTask(t.Context(), task("task-2", "workflow-1", dumpInput(t, "dump")))

	requireNonRetryable(t, err, "key must decode to 32 bytes")
}

func TestRunEncryptTaskWithoutTheDump(t *testing.T) {
	input := dumpInput(t, "dump")
	input["dump_path"] = filepath.Join(t.TempDir(), "missing.sql")

	_, err := NewPipeline(testConfig(t), nil).RunEncryptTask(t.Context(), task("task-2", "workflow-1", input))

	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expected the missing dump as the error, got %v", err)
	}
}

func TestRunEncryptTaskRemovesThePlainDump(t *testing.T) {
	input := dumpInput(t, "INSERT INTO people VALUES ('Alice');")

	if _, err := NewPipeline(testConfig(t), nil).RunEncryptTask(t.Context(), task("task-2", "workflow-1",
		input)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	reason := "the plain dump stays on disk after encryption, until the cleanup task, which doesn't run when a " +
		"later task fails."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if _, err := os.Stat(input["dump_path"].(string)); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("expected the plain dump to be removed, got %v", err)
		}
	})
}

// encryptOutputFor is the encryption task's output for the input.
func encryptOutputFor(input map[string]any, workflowID, encPath string) localmodel.EncryptTaskOutput {
	return localmodel.EncryptTaskOutput{
		Timestamp:         input["timestamp"].(string),
		WorkflowID:        workflowID,
		BaseDir:           input["base_dir"].(string),
		EncryptedPath:     encPath,
		EncryptedFileName: "backup.sql.enc",
		DumpFileName:      input["dump_file_name"].(string),
	}
}

// encryptedInput writes an encrypted file into a new work folder and returns the compress task's input for it.
func encryptedInput(t *testing.T, content string) map[string]any {
	t.Helper()

	baseDir := t.TempDir()
	encPath := filepath.Join(baseDir, "backup.sql.enc")
	writeFile(t, encPath, content)
	return map[string]any{
		"encrypted_path":      encPath,
		"base_dir":            baseDir,
		"timestamp":           "20261126T230000",
		"dump_file_name":      "backup.sql",
		"encrypted_file_name": "backup.sql.enc",
	}
}

func TestRunCompressTaskGzipsTheFile(t *testing.T) {
	input := encryptedInput(t, "encrypted bytes")

	output, err := NewPipeline(testConfig(t), nil).RunCompressTask(t.Context(), task("task-3", "workflow-1", input))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	baseDir := input["base_dir"].(string)
	gzipPath := filepath.Join(baseDir, "backup.sql.enc.gz")
	if output.Timestamp != "20261126T230000" || output.WorkflowID != "workflow-1" || output.BaseDir != baseDir ||
		output.CompressedPath != gzipPath || output.CompressedFileName != "backup.sql.enc.gz" {
		t.Errorf("unexpected output %+v", output)
	}
	if content := gunzip(t, gzipPath); string(content) != "encrypted bytes" {
		t.Errorf("gunzipped = %q", content)
	}
	requirePrivate(t, gzipPath, 0o600)
}

func TestRunCompressTaskReplacesAnEarlierArchive(t *testing.T) {
	input := encryptedInput(t, "new")
	writeFile(t, filepath.Join(input["base_dir"].(string), "backup.sql.enc.gz"), strings.Repeat("old ", 1000))

	output, err := NewPipeline(testConfig(t), nil).RunCompressTask(t.Context(), task("task-3", "workflow-1", input))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if content := gunzip(t, output.CompressedPath); string(content) != "new" {
		t.Errorf("gunzipped = %q, want only the new content", content)
	}
}

func TestRunCompressTaskRequiresItsInput(t *testing.T) {
	for _, key := range []string{"encrypted_path", "base_dir", "timestamp"} {
		t.Run(key, func(t *testing.T) {
			input := encryptedInput(t, "encrypted")
			delete(input, key)

			_, err := NewPipeline(testConfig(t), nil).RunCompressTask(t.Context(), task("task-3", "workflow-1", input))

			requireNonRetryable(t, err, "missing required input key: "+key)
		})
	}
}

func TestRunCompressTaskWithoutTheEncryptedFile(t *testing.T) {
	input := encryptedInput(t, "encrypted")
	input["encrypted_path"] = filepath.Join(t.TempDir(), "missing.enc")

	_, err := NewPipeline(testConfig(t), nil).RunCompressTask(t.Context(), task("task-3", "workflow-1", input))

	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expected the missing file as the error, got %v", err)
	}
}

func TestRunCompressTaskWithoutTheWorkFolder(t *testing.T) {
	input := encryptedInput(t, "encrypted")
	input["base_dir"] = filepath.Join(t.TempDir(), "missing")

	_, err := NewPipeline(testConfig(t), nil).RunCompressTask(t.Context(), task("task-3", "workflow-1", input))

	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expected the missing folder as the error, got %v", err)
	}
}

func TestBackupIsSmallerThanTheDump(t *testing.T) {
	// A SQL dump is mostly repeated text, which gzip shrinks many times over.
	var dump strings.Builder
	for i := range 2000 {
		fmt.Fprintf(&dump, "INSERT INTO public.people (id, name) VALUES (%d, 'person %d');\n", i, i)
	}
	pipeline := NewPipeline(testConfig(t), nil)

	encrypted, err := pipeline.RunEncryptTask(t.Context(), task("task-2", "workflow-1", dumpInput(t, dump.String())))
	if err != nil {
		t.Fatalf("failed to encrypt: %v", err)
	}
	compressed, err := pipeline.RunCompressTask(t.Context(), task("task-3", "workflow-1", map[string]any{
		"encrypted_path": encrypted.EncryptedPath,
		"base_dir":       encrypted.BaseDir,
		"timestamp":      encrypted.Timestamp,
	}))
	if err != nil {
		t.Fatalf("failed to compress: %v", err)
	}

	backupSize := len(readFile(t, compressed.CompressedPath))
	reason := "the dump is compressed after it is encrypted, and encrypted data doesn't compress."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if backupSize > dump.Len()/3 {
			t.Errorf("the backup is %d bytes for a %d-byte dump, expected it at least three times smaller",
				backupSize, dump.Len())
		}
	})
}

// compressedInput writes a gzip file into a new work folder and returns the upload task's input for it.
func compressedInput(t *testing.T) map[string]any {
	t.Helper()

	baseDir := t.TempDir()
	gzipPath := filepath.Join(baseDir, "backup.sql.enc.gz")
	writeFile(t, gzipPath, "gzip")
	return map[string]any{
		"compressed_path":      gzipPath,
		"base_dir":             baseDir,
		"timestamp":            "20261126T230000",
		"dump_file_name":       "backup.sql",
		"encrypted_file_name":  "backup.sql.enc",
		"compressed_file_name": "backup.sql.enc.gz",
	}
}

func TestRunUploadTaskUploadsTheBackup(t *testing.T) {
	testutil.CaptureLog(t)
	uploader := &fakeUploader{link: "https://pub-backups.r2.dev/backup"}
	input := compressedInput(t)

	started := time.Now()
	output, err := NewPipeline(testConfig(t), uploader).RunUploadTask(t.Context(), task("task-4", "workflow-1", input))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	uploads := uploader.calls()
	if len(uploads) != 1 {
		t.Fatalf("expected one upload, got %+v", uploads)
	}
	upload := uploads[0]
	wantKey := "db-backup/20261126T230000/workflow-1-task-4.sql.enc.gz"
	if upload.key != wantKey || upload.path != input["compressed_path"] {
		t.Errorf("uploaded %s to %s, want %s to %s", upload.path, upload.key, input["compressed_path"], wantKey)
	}
	if upload.opts != (objectstore.UploadOptions{ContentType: "application/gzip"}) {
		t.Errorf("upload options = %+v", upload.opts)
	}

	want := localmodel.UploadTaskOutput{
		ObjectKey:      wantKey,
		ObjectPath:     "https://pub-backups.r2.dev/backup",
		WorkflowID:     "workflow-1",
		TaskID:         "task-4",
		DumpFileName:   "backup.sql",
		EncryptedName:  "backup.sql.enc",
		CompressedName: "backup.sql.enc.gz",
		UploadedAtUnix: output.UploadedAtUnix,
	}
	if output != want {
		t.Errorf("output = %+v, want %+v", output, want)
	}
	if output.UploadedAtUnix < started.Unix() || output.UploadedAtUnix > time.Now().Unix() {
		t.Errorf("UploadedAtUnix = %d, want the upload time", output.UploadedAtUnix)
	}
}

func TestRunUploadTaskLimitsTheUploadTime(t *testing.T) {
	testutil.CaptureLog(t)
	cfg := testConfig(t)
	cfg.UploadTimeout = 5 * time.Minute
	uploader := &fakeUploader{}

	started := time.Now()
	if _, err := NewPipeline(cfg, uploader).RunUploadTask(t.Context(), task("task-4", "workflow-1",
		compressedInput(t))); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	finished := time.Now()

	upload := uploader.calls()[0]
	if !upload.hasDeadline {
		t.Fatal("expected the upload to have a deadline")
	}
	if upload.deadline.Before(started.Add(cfg.UploadTimeout)) ||
		upload.deadline.After(finished.Add(cfg.UploadTimeout)) {
		t.Errorf("the upload may take %s, want DB_BACKUP_UPLOAD_TIMEOUT_SECONDS", upload.deadline.Sub(started))
	}
}

func TestRunUploadTaskWithoutTheFileNames(t *testing.T) {
	testutil.CaptureLog(t)
	input := compressedInput(t)
	delete(input, "dump_file_name")
	input["encrypted_file_name"] = nil
	input["compressed_file_name"] = "  "

	output, err := NewPipeline(testConfig(t), &fakeUploader{}).RunUploadTask(t.Context(), task("task-4",
		"workflow-1", input))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if output.DumpFileName != "" || output.EncryptedName != "" || output.CompressedName != "" {
		t.Errorf("expected empty file names, got %+v", output)
	}
}

func TestRunUploadTaskRequiresItsInput(t *testing.T) {
	for _, key := range []string{"compressed_path", "timestamp", "base_dir"} {
		t.Run(key, func(t *testing.T) {
			logs := testutil.CaptureLog(t)
			uploader := &fakeUploader{}
			input := compressedInput(t)
			delete(input, key)

			_, err := NewPipeline(testConfig(t), uploader).RunUploadTask(t.Context(), task("task-4", "workflow-1",
				input))

			requireNonRetryable(t, err, "missing required input key: "+key)
			if len(uploader.calls()) != 0 {
				t.Error("expected no upload")
			}
			if !strings.Contains(logs.String(), "input error: workflow_id=workflow-1 task_id=task-4 key="+key) {
				t.Errorf("expected the input error in the log, got:\n%s", logs.String())
			}
		})
	}
}

func TestRunUploadTaskReturnsTheUploadError(t *testing.T) {
	logs := testutil.CaptureLog(t)
	uploader := &fakeUploader{err: errors.New("bucket not found")}

	output, err := NewPipeline(testConfig(t), uploader).RunUploadTask(t.Context(), task("task-4", "workflow-1",
		compressedInput(t)))

	if err == nil || err.Error() != "bucket not found" {
		t.Fatalf("expected the upload error, got %v", err)
	}
	if output != (localmodel.UploadTaskOutput{}) {
		t.Errorf("expected no output with the error, got %+v", output)
	}
	// An outage of the store is worth another try.
	if _, ok := errors.AsType[*conductormodel.NonRetryableError](err); ok {
		t.Errorf("expected a retryable error, got %v", err)
	}
	if !strings.Contains(logs.String(), "upload failed") || !strings.Contains(logs.String(), "timeout=30s") {
		t.Errorf("expected the failed upload in the log, got:\n%s", logs.String())
	}
}

func TestRunUploadTaskLeavesAMissingFileToTheUploader(t *testing.T) {
	logs := testutil.CaptureLog(t)
	uploader := &fakeUploader{err: errors.New("failed to open")}
	input := compressedInput(t)
	input["compressed_path"] = filepath.Join(t.TempDir(), "missing.gz")

	if _, err := NewPipeline(testConfig(t), uploader).RunUploadTask(t.Context(), task("task-4", "workflow-1",
		input)); err == nil {
		t.Fatal("expected the uploader's error")
	}

	if !strings.Contains(logs.String(), "unable to stat compressed file") {
		t.Errorf("expected the missing file in the log, got:\n%s", logs.String())
	}
}

func TestRunCleanupTaskRemovesTheWorkFolder(t *testing.T) {
	baseDir := filepath.Join(t.TempDir(), "workflow-1")
	if err := os.MkdirAll(filepath.Join(baseDir, "nested"), 0o700); err != nil {
		t.Fatalf("failed to make the folder: %v", err)
	}
	writeFile(t, filepath.Join(baseDir, "backup.sql"), "dump")

	started := time.Now().Unix()
	output, err := NewPipeline(testConfig(t), nil).RunCleanupTask(t.Context(), task("task-5", "workflow-1",
		map[string]any{"base_dir": baseDir}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if _, err := os.Stat(baseDir); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("expected the folder to be removed, got %v", err)
	}
	if output.WorkflowID != "workflow-1" || output.DeletedBaseDir != baseDir || output.CleanedAtUnix < started {
		t.Errorf("unexpected output %+v", output)
	}
}

func TestRunCleanupTaskWithAMissingFolder(t *testing.T) {
	baseDir := filepath.Join(t.TempDir(), "already-removed")

	// A retried cleanup finds the folder already gone, which is fine.
	if _, err := NewPipeline(testConfig(t), nil).RunCleanupTask(t.Context(), task("task-5", "workflow-1",
		map[string]any{"base_dir": baseDir})); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestRunCleanupTaskRequiresTheFolder(t *testing.T) {
	_, err := NewPipeline(testConfig(t), nil).RunCleanupTask(t.Context(), task("task-5", "workflow-1", nil))

	requireNonRetryable(t, err, "missing required input key: base_dir")
}

func TestTaskFailuresAreReportedToSentry(t *testing.T) {
	sentry := testutil.NewFakeSentry(t)
	logging.InitSentry(sentry.DSN(), "db_backup_worker")
	t.Cleanup(func() { logging.InitSentry("", "") })
	cfg := testConfig(t)
	cfg.Timezone = "Mars/Olympus_Mons"

	if _, err := NewPipeline(cfg, nil).RunPgDumpTask(t.Context(), task("task-1", "workflow-1", nil)); err == nil {
		t.Fatal("expected the task to fail")
	}

	reason := "task errors only go back to Conductor and the log, so a failing backup is never reported."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, 2*time.Second); len(events) == 0 {
			t.Error("expected the failure in Sentry")
		}
	})
}

func TestRequiredInput(t *testing.T) {
	testCases := []struct {
		name    string
		input   map[string]any
		want    string
		wantErr string
	}{
		{name: "text", input: map[string]any{"key": "value"}, want: "value"},
		{name: "trimmed", input: map[string]any{"key": "  value\n"}, want: "value"},
		{name: "number", input: map[string]any{"key": 42}, want: "42"},
		{name: "missing", input: map[string]any{}, wantErr: "missing required input key: key"},
		{name: "no input", input: nil, wantErr: "missing required input key: key"},
		{name: "empty", input: map[string]any{"key": ""}, wantErr: "empty required input key: key"},
		{name: "spaces", input: map[string]any{"key": "   "}, wantErr: "empty required input key: key"},
		// Conductor sends null for an output an earlier task didn't set.
		{name: "null", input: map[string]any{"key": nil}, wantErr: "empty required input key: key"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			got, err := requiredInput(task("task", "workflow", testCase.input), "key")

			if testCase.wantErr != "" {
				requireNonRetryable(t, err, testCase.wantErr)
				return
			}
			if err != nil || got != testCase.want {
				t.Fatalf("requiredInput() = %q, %v, want %q", got, err, testCase.want)
			}
		})
	}
}

func TestOptionalInput(t *testing.T) {
	testCases := []struct {
		name  string
		input map[string]any
		want  string
	}{
		{name: "text", input: map[string]any{"key": "value"}, want: "value"},
		{name: "trimmed", input: map[string]any{"key": " value "}, want: "value"},
		{name: "number", input: map[string]any{"key": 7}, want: "7"},
		{name: "missing", input: map[string]any{}, want: ""},
		{name: "null", input: map[string]any{"key": nil}, want: ""},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			if got := optionalInput(task("task", "workflow", testCase.input), "key"); got != testCase.want {
				t.Fatalf("optionalInput() = %q, want %q", got, testCase.want)
			}
		})
	}
}

func TestEncodeKeyBase64(t *testing.T) {
	key := config.Config{EncryptionKeyRaw: EncodeKeyBase64([]byte(testKey))}

	decoded, err := key.DecodedEncryptionKey()
	if err != nil || string(decoded) != testKey {
		t.Fatalf("expected the key back, got %q, %v", decoded, err)
	}
}
