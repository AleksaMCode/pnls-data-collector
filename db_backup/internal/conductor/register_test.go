package conductor

import (
	"db_backup/internal/config"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"sync"
	"testing"

	"github.com/conductor-sdk/conductor-go/sdk/client"
	"github.com/conductor-sdk/conductor-go/sdk/model"
	"github.com/conductor-sdk/conductor-go/sdk/settings"
)

// moduleRoot is the db_backup folder, where the worker runs and finds workflows/.
func moduleRoot(t *testing.T) string {
	t.Helper()

	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot find the test file")
	}
	return filepath.Join(filepath.Dir(file), "..", "..")
}

// request is a request the fake Conductor received.
type request struct {
	method, path, query string
	body                []byte
}

// fakeConductor answers the metadata API with the status set for each method and path, 200 by default.
type fakeConductor struct {
	server   *httptest.Server
	mu       sync.Mutex
	answers  map[string]answer
	requests []request
}

type answer struct {
	status int
	body   string
}

func newFakeConductor(t *testing.T) *fakeConductor {
	t.Helper()

	fake := &fakeConductor{answers: map[string]answer{}}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		fake.mu.Lock()
		fake.requests = append(fake.requests, request{
			method: r.Method, path: r.URL.Path, query: r.URL.RawQuery, body: body,
		})
		reply, ok := fake.answers[r.Method+" "+r.URL.Path]
		fake.mu.Unlock()
		if !ok {
			reply = answer{status: http.StatusOK}
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(reply.status)
		_, _ = w.Write([]byte(reply.body))
	}))
	t.Cleanup(fake.server.Close)
	return fake
}

func (f *fakeConductor) answer(method, path string, status int, body string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.answers[method+" /api"+path] = answer{status: status, body: body}
}

func (f *fakeConductor) client() *client.APIClient {
	return client.NewAPIClient(nil, settings.NewHttpSettings(f.server.URL+"/api"))
}

func (f *fakeConductor) received() []request {
	f.mu.Lock()
	defer f.mu.Unlock()
	return slices.Clone(f.requests)
}

func (f *fakeConductor) find(method, path string) []request {
	var found []request
	for _, r := range f.received() {
		if r.method == method && r.path == "/api"+path {
			found = append(found, r)
		}
	}
	return found
}

func testConfig() config.Config {
	return config.Config{WorkflowName: "db_backup_workflow", WorkflowVersion: 1}
}

// writeDefinitions writes the definition files into a new folder, moves there until the test ends, and returns it.
func writeDefinitions(t *testing.T, taskDefs, workflowDef string) string {
	t.Helper()

	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, "workflows"), 0o700); err != nil {
		t.Fatalf("failed to make workflows/: %v", err)
	}
	for name, content := range map[string]string{"task_definition.json": taskDefs, "workflow_definition.json": workflowDef} {
		if content == "" {
			continue
		}
		if err := os.WriteFile(filepath.Join(dir, "workflows", name), []byte(content), 0o600); err != nil {
			t.Fatalf("failed to write %s: %v", name, err)
		}
	}
	t.Chdir(dir)
	return dir
}

func taskNames(t *testing.T, body []byte) []string {
	t.Helper()

	var defs []model.TaskDef
	if err := json.Unmarshal(body, &defs); err != nil {
		t.Fatalf("failed to read the task definitions sent: %v", err)
	}
	names := make([]string, 0, len(defs))
	for _, def := range defs {
		names = append(names, def.Name)
	}
	return names
}

var allTasks = []string{
	"pg_dump_task", "encryption_task", "compress_task", "upload_to_r2_task", "cleanup_local_files_task",
}

func TestRegisterAllRegistersTheTasksAndTheWorkflow(t *testing.T) {
	fake := newFakeConductor(t)
	t.Chdir(moduleRoot(t))

	if err := RegisterAll(t.Context(), testConfig(), fake.client()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	registered := fake.find(http.MethodPost, "/metadata/taskdefs")
	if len(registered) != 1 {
		t.Fatalf("expected one task registration, got %+v", fake.received())
	}
	if names := taskNames(t, registered[0].body); !slices.Equal(names, allTasks) {
		t.Errorf("registered the tasks %v, want %v", names, allTasks)
	}
	if updates := fake.find(http.MethodPut, "/metadata/taskdefs"); len(updates) != 0 {
		t.Errorf("expected no updates, got %d", len(updates))
	}

	workflows := fake.find(http.MethodPost, "/metadata/workflow")
	if len(workflows) != 1 {
		t.Fatalf("expected one workflow registration, got %+v", fake.received())
	}
	if workflows[0].query != "overwrite=true" {
		t.Errorf("query = %q, want the workflow overwritten", workflows[0].query)
	}
	var workflow model.WorkflowDef
	if err := json.Unmarshal(workflows[0].body, &workflow); err != nil {
		t.Fatalf("failed to read the workflow sent: %v", err)
	}
	if workflow.Name != "db_backup_workflow" || workflow.Version != 1 || len(workflow.Tasks) != len(allTasks) {
		t.Errorf("unexpected workflow %s v%d with %d tasks", workflow.Name, workflow.Version, len(workflow.Tasks))
	}
}

func TestRegisterAllUpdatesTasksThatExist(t *testing.T) {
	fake := newFakeConductor(t)
	fake.answer(http.MethodPost, "/metadata/taskdefs", http.StatusConflict, `{"message":"Task already exists"}`)
	t.Chdir(moduleRoot(t))

	if err := RegisterAll(t.Context(), testConfig(), fake.client()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	updates := fake.find(http.MethodPut, "/metadata/taskdefs")
	var updated []string
	for _, update := range updates {
		var def model.TaskDef
		if err := json.Unmarshal(update.body, &def); err != nil {
			t.Fatalf("failed to read the update: %v", err)
		}
		updated = append(updated, def.Name)
	}
	if !slices.Equal(updated, allTasks) {
		t.Errorf("updated %v, want %v", updated, allTasks)
	}
	if len(fake.find(http.MethodPost, "/metadata/workflow")) != 1 {
		t.Error("expected the workflow to be registered after the updates")
	}
}

func TestRegisterAllReportsAFailedUpdate(t *testing.T) {
	fake := newFakeConductor(t)
	fake.answer(http.MethodPost, "/metadata/taskdefs", http.StatusConflict, "")
	fake.answer(http.MethodPut, "/metadata/taskdefs", http.StatusInternalServerError, `{"message":"down"}`)
	t.Chdir(moduleRoot(t))

	err := RegisterAll(t.Context(), testConfig(), fake.client())

	if err == nil || !strings.Contains(err.Error(), "update task definition pg_dump_task") {
		t.Fatalf("expected the failed update, got %v", err)
	}
	if len(fake.find(http.MethodPost, "/metadata/workflow")) != 0 {
		t.Error("expected the workflow not to be registered")
	}
}

func TestRegisterAllAcceptsAnExistingWorkflow(t *testing.T) {
	fake := newFakeConductor(t)
	fake.answer(http.MethodPost, "/metadata/workflow", http.StatusConflict,
		`{"message":"Workflow with db_backup_workflow.1 already exists!"}`)
	t.Chdir(moduleRoot(t))

	if err := RegisterAll(t.Context(), testConfig(), fake.client()); err != nil {
		t.Fatalf("expected an existing workflow to be fine, got %v", err)
	}
}

func TestRegisterAllReportsAFailedWorkflowRegistration(t *testing.T) {
	fake := newFakeConductor(t)
	fake.answer(http.MethodPost, "/metadata/workflow", http.StatusBadRequest, `{"message":"invalid workflow"}`)
	t.Chdir(moduleRoot(t))

	err := RegisterAll(t.Context(), testConfig(), fake.client())

	if err == nil || !strings.Contains(err.Error(), "register workflow definition") ||
		!strings.Contains(err.Error(), "invalid workflow") {
		t.Fatalf("expected the failed registration, got %v", err)
	}
}

func TestRegisterAllWithoutConductor(t *testing.T) {
	fake := newFakeConductor(t)
	apiClient := fake.client()
	fake.server.Close()
	t.Chdir(moduleRoot(t))

	if err := RegisterAll(t.Context(), testConfig(), apiClient); err == nil {
		t.Fatal("expected an error when Conductor can't be reached")
	}
}

func TestRegisterAllTakesTheWorkflowNameAndVersionFromTheConfig(t *testing.T) {
	fake := newFakeConductor(t)
	writeDefinitions(t, `[{"name":"pg_dump_task"}]`, `{"tasks":[]}`)
	cfg := config.Config{WorkflowName: "nightly_backup", WorkflowVersion: 4}

	if err := RegisterAll(t.Context(), cfg, fake.client()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	var workflow model.WorkflowDef
	if err := json.Unmarshal(fake.find(http.MethodPost, "/metadata/workflow")[0].body, &workflow); err != nil {
		t.Fatalf("failed to read the workflow sent: %v", err)
	}
	if workflow.Name != "nightly_backup" || workflow.Version != 4 {
		t.Errorf("registered %s v%d, want nightly_backup v4", workflow.Name, workflow.Version)
	}
}

func TestRegisterAllReportsBadDefinitionFiles(t *testing.T) {
	testCases := []struct {
		name, taskDefs, workflowDef, wantErr string
	}{
		{name: "no task definitions", wantErr: "read task definitions"},
		{name: "invalid task definitions", taskDefs: "{", wantErr: "parse task definitions"},
		{name: "no workflow definition", taskDefs: `[{"name":"pg_dump_task"}]`, wantErr: "read workflow definition"},
		{
			name:        "invalid workflow definition",
			taskDefs:    `[{"name":"pg_dump_task"}]`,
			workflowDef: `{"tasks":`,
			wantErr:     "parse workflow definition",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			fake := newFakeConductor(t)
			writeDefinitions(t, testCase.taskDefs, testCase.workflowDef)

			err := RegisterAll(t.Context(), testConfig(), fake.client())

			if err == nil || !strings.Contains(err.Error(), testCase.wantErr) {
				t.Fatalf("expected %q, got %v", testCase.wantErr, err)
			}
		})
	}
}

func TestReadTaskDefs(t *testing.T) {
	testCases := []struct {
		name, content string
		want          []string
		wantErr       string
	}{
		{name: "list", content: `[{"name":"a"},{"name":"b"}]`, want: []string{"a", "b"}},
		{name: "single definition", content: `{"name":"a"}`, want: []string{"a"}},
		// An empty list is read as a single definition, which fails.
		{name: "empty list", content: `[]`, wantErr: "parse task definitions"},
		{name: "not JSON", content: `name: a`, wantErr: "parse task definitions"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "tasks.json")
			if err := os.WriteFile(path, []byte(testCase.content), 0o600); err != nil {
				t.Fatalf("failed to write the file: %v", err)
			}

			defs, err := readTaskDefs(path)

			if testCase.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), testCase.wantErr) {
					t.Fatalf("expected %q, got %v", testCase.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			var names []string
			for _, def := range defs {
				names = append(names, def.Name)
			}
			if !slices.Equal(names, testCase.want) {
				t.Fatalf("read %v, want %v", names, testCase.want)
			}
		})
	}
}

func TestIsAlreadyExistsErr(t *testing.T) {
	testCases := []struct {
		err  error
		want bool
	}{
		{err: nil, want: false},
		{err: errors.New("Workflow Already Exists"), want: true},
		{err: errors.New("error: , body: {\"message\":\"already exists\"}"), want: true},
		{err: errors.New("connection refused"), want: false},
	}

	for _, testCase := range testCases {
		if got := isAlreadyExistsErr(testCase.err); got != testCase.want {
			t.Errorf("isAlreadyExistsErr(%v) = %v, want %v", testCase.err, got, testCase.want)
		}
	}
}
