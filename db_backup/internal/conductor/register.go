package conductor

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"db_backup/internal/config"

	"github.com/conductor-sdk/conductor-go/sdk/client"
	"github.com/conductor-sdk/conductor-go/sdk/model"
)

func RegisterAll(ctx context.Context, cfg config.Config, apiClient *client.APIClient) error {
	metadataClient := client.NewMetadataClient(apiClient)

	taskDefs, err := readTaskDefs("workflows/task_definition.json")
	if err != nil {
		return err
	}
	if err := registerTaskDefs(ctx, metadataClient, taskDefs); err != nil {
		return err
	}

	workflowDef, err := readWorkflowDef("workflows/workflow_definition.json")
	if err != nil {
		return err
	}
	if workflowDef.Name == "" {
		workflowDef.Name = cfg.WorkflowName
	}
	if workflowDef.Version == 0 {
		workflowDef.Version = cfg.WorkflowVersion
	}
	if _, err := metadataClient.RegisterWorkflowDef(ctx, true, workflowDef); err != nil {
		// Workflow may already exist from a previous run; treat this as non-fatal.
		if !isAlreadyExistsErr(err) {
			return fmt.Errorf("register workflow definition: %w", err)
		}
	}

	// Scheduling is handled outside the worker (cron on host).
	// TODO: Add schedule registration in the future.
	return nil
}

func registerTaskDefs(ctx context.Context, metadataClient client.MetadataClient, taskDefs []model.TaskDef) error {
	if _, err := metadataClient.RegisterTaskDef(ctx, taskDefs); err == nil {
		return nil
	}

	for _, taskDef := range taskDefs {
		if _, err := metadataClient.UpdateTaskDef(ctx, taskDef); err != nil {
			return fmt.Errorf("update task definition %s: %w", taskDef.Name, err)
		}
	}
	return nil
}

func readTaskDefs(path string) ([]model.TaskDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read task definitions: %w", err)
	}

	var list []model.TaskDef
	if err := json.Unmarshal(data, &list); err == nil && len(list) > 0 {
		return list, nil
	}

	var single model.TaskDef
	if err := json.Unmarshal(data, &single); err != nil {
		return nil, fmt.Errorf("parse task definitions: %w", err)
	}
	return []model.TaskDef{single}, nil
}

func readWorkflowDef(path string) (model.WorkflowDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return model.WorkflowDef{}, fmt.Errorf("read workflow definition: %w", err)
	}
	var def model.WorkflowDef
	if err := json.Unmarshal(data, &def); err != nil {
		return model.WorkflowDef{}, fmt.Errorf("parse workflow definition: %w", err)
	}
	return def, nil
}

func readSchedule(path string) (model.SaveScheduleRequest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return model.SaveScheduleRequest{}, fmt.Errorf("read schedule definition: %w", err)
	}
	var req model.SaveScheduleRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return model.SaveScheduleRequest{}, fmt.Errorf("parse schedule definition: %w", err)
	}
	return req, nil
}

func isAlreadyExistsErr(err error) bool {
	if err == nil {
		return false
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "already exists")
}
