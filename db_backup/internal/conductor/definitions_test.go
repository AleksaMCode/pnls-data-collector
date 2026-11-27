package conductor

import (
	"db_backup/internal/backup"
	localmodel "db_backup/internal/model"
	"path/filepath"
	"reflect"
	"regexp"
	"slices"
	"strings"
	"testing"

	"github.com/conductor-sdk/conductor-go/sdk/model"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// workerOutputs are the outputs of the tasks the worker runs, by task name.
var workerOutputs = map[string]any{
	backup.TaskPgDumpName:   localmodel.PgDumpTaskOutput{},
	backup.TaskEncryptName:  localmodel.EncryptTaskOutput{},
	backup.TaskCompressName: localmodel.CompressTaskOutput{},
	backup.TaskUploadName:   localmodel.UploadTaskOutput{},
	backup.TaskCleanupName:  localmodel.CleanupTaskOutput{},
}

// outputReference matches ${task_ref.output.key} in a workflow.
var outputReference = regexp.MustCompile(`^\$\{([a-z0-9_]+)\.output\.([a-z0-9_]+)\}$`)

// jsonFields are the JSON names of the struct's fields, which are the keys of the task's output in Conductor.
func jsonFields(value any) []string {
	var fields []string
	for field := range reflect.TypeOf(value).Fields() {
		name, _, _ := strings.Cut(field.Tag.Get("json"), ",")
		fields = append(fields, name)
	}
	return fields
}

func readDefinitions(t *testing.T) (map[string]model.TaskDef, model.WorkflowDef) {
	t.Helper()

	dir := filepath.Join(moduleRoot(t), "workflows")
	taskDefs, err := readTaskDefs(filepath.Join(dir, "task_definition.json"))
	if err != nil {
		t.Fatalf("failed to read the task definitions: %v", err)
	}
	workflow, err := readWorkflowDef(filepath.Join(dir, "workflow_definition.json"))
	if err != nil {
		t.Fatalf("failed to read the workflow: %v", err)
	}
	byName := map[string]model.TaskDef{}
	for _, def := range taskDefs {
		byName[def.Name] = def
	}
	return byName, workflow
}

func TestEveryTaskHasAWorker(t *testing.T) {
	taskDefs, workflow := readDefinitions(t)

	for name := range taskDefs {
		if _, ok := workerOutputs[name]; !ok {
			t.Errorf("the task %s is defined, but no worker runs it", name)
		}
	}
	for _, workflowTask := range workflow.Tasks {
		if _, ok := taskDefs[workflowTask.Name]; !ok {
			t.Errorf("the workflow runs %s, which isn't defined", workflowTask.Name)
		}
		if workflowTask.Type_ != "SIMPLE" {
			t.Errorf("%s has the type %s, want SIMPLE, as the worker runs it", workflowTask.Name, workflowTask.Type_)
		}
	}
	if len(workflow.Tasks) != len(workerOutputs) {
		t.Errorf("the workflow runs %d tasks, want the %d the worker runs", len(workflow.Tasks), len(workerOutputs))
	}
}

func TestTaskOutputKeysAreWhatTheWorkersReturn(t *testing.T) {
	taskDefs, _ := readDefinitions(t)

	for name, output := range workerOutputs {
		t.Run(name, func(t *testing.T) {
			check := func(t testutil.TB) {
				fields := jsonFields(output)
				for _, key := range taskDefs[name].OutputKeys {
					if !slices.Contains(fields, key) {
						t.Errorf("%s declares the output %s, which %T doesn't have", name, key, output)
					}
				}
				for _, field := range fields {
					if !slices.Contains(taskDefs[name].OutputKeys, field) {
						t.Errorf("%s returns %s, which its definition doesn't declare", name, field)
					}
				}
			}

			if name != backup.TaskCompressName {
				check(t)
				return
			}
			reason := "compress_task declares dump_file_name and encrypted_file_name as outputs, but " +
				"CompressTaskOutput doesn't have them, so the upload gets empty file names."
			testutil.ExpectFailure(t, reason, check)
		})
	}
}

func TestWorkflowInputsAreTheTasksInputKeys(t *testing.T) {
	taskDefs, workflow := readDefinitions(t)

	for _, workflowTask := range workflow.Tasks {
		var keys []string
		for key := range workflowTask.InputParameters {
			keys = append(keys, key)
		}
		slices.Sort(keys)
		declared := slices.Sorted(slices.Values(taskDefs[workflowTask.Name].InputKeys))
		if !slices.Equal(keys, declared) {
			t.Errorf("the workflow gives %s the inputs %v, but its definition declares %v",
				workflowTask.Name, keys, declared)
		}
	}
}

func TestWorkflowReferencesOutputsOfEarlierTasks(t *testing.T) {
	_, workflow := readDefinitions(t)

	for index, workflowTask := range workflow.Tasks {
		t.Run(workflowTask.Name, func(t *testing.T) {
			check := func(t testutil.TB) {
				for key, value := range workflowTask.InputParameters {
					checkReference(t, workflow.Tasks[:index], workflowTask.Name+"."+key, value)
				}
			}

			if workflowTask.Name != backup.TaskUploadName {
				check(t)
				return
			}
			reason := "upload_to_r2_task reads dump_file_name and encrypted_file_name from compress_task, " +
				"whose output doesn't have them."
			testutil.ExpectFailure(t, reason, check)
		})
	}
}

func TestWorkflowOutputsAreUploadOutputs(t *testing.T) {
	_, workflow := readDefinitions(t)

	for key, value := range workflow.OutputParameters {
		checkReference(t, workflow.Tasks, "workflow output "+key, value)
	}
	if _, ok := workflow.OutputParameters["object_key"]; !ok {
		t.Error("expected the object key in the workflow output, which Airflow reads")
	}
}

// checkReference fails unless value is ${ref.output.key}, where ref is one of the tasks and key is in its output.
func checkReference(t testutil.TB, tasks []model.WorkflowTask, name string, value any) {
	t.Helper()

	text, _ := value.(string)
	match := outputReference.FindStringSubmatch(text)
	if match == nil {
		t.Errorf("%s = %v, want ${task_ref.output.key}", name, value)
		return
	}
	index := slices.IndexFunc(tasks, func(task model.WorkflowTask) bool { return task.TaskReferenceName == match[1] })
	if index < 0 {
		t.Errorf("%s reads %s, which doesn't run before it", name, match[1])
		return
	}
	output := workerOutputs[tasks[index].Name]
	if !slices.Contains(jsonFields(output), match[2]) {
		t.Errorf("%s reads %s from %s, whose output %T doesn't have it", name, match[2], tasks[index].Name, output)
	}
}
