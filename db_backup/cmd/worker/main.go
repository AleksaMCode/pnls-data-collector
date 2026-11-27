package main

import (
	"context"
	"db_backup/internal/backup"
	"db_backup/internal/conductor"
	"db_backup/internal/config"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"

	conductorclient "github.com/conductor-sdk/conductor-go/sdk/client"
	conductormodel "github.com/conductor-sdk/conductor-go/sdk/model"
	"github.com/conductor-sdk/conductor-go/sdk/worker"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
)

// defaultServiceName names the worker in Sentry when SERVICE_NAME isn't set.
const defaultServiceName = "db_backup_worker"

func main() {
	initSentry(os.Getenv("SENTRY_DSN"), os.Getenv("SERVICE_NAME"))

	cfg, err := config.Load()
	if err != nil {
		logging.Fatal(fmt.Sprintf("configuration error: %v", err))
	}

	// Keep SDK config in sync with local config values.
	_ = os.Setenv("CONDUCTOR_SERVER_URL", cfg.ConductorServerURL)
	_ = os.Setenv("TZ", cfg.Timezone)

	ctx := context.Background()
	apiClient := conductorclient.NewAPIClientFromEnv()

	if err := conductor.RegisterAll(ctx, cfg, apiClient); err != nil {
		logging.Fatal(fmt.Sprintf("registration error: %v", err))
	}

	store, err := objectstore.New(ctx, cfg.ObjectStore())
	if err != nil {
		logging.Fatal(fmt.Sprintf("r2 client init error: %v", err))
	}
	pipeline := backup.NewPipeline(cfg, store)

	taskRunner := worker.NewTaskRunnerWithApiClient(apiClient)
	pgDumpHandler := func(task *conductormodel.Task) (any, error) {
		return pipeline.RunPgDumpTask(ctx, task)
	}
	encryptHandler := func(task *conductormodel.Task) (any, error) {
		return pipeline.RunEncryptTask(ctx, task)
	}
	compressHandler := func(task *conductormodel.Task) (any, error) {
		return pipeline.RunCompressTask(ctx, task)
	}
	uploadHandler := func(task *conductormodel.Task) (any, error) {
		log.Printf(
			"upload handler started: workflow_id=%s task_id=%s retry_count=%d",
			task.WorkflowInstanceId,
			task.TaskId,
			task.RetryCount,
		)
		output, err := pipeline.RunUploadTask(ctx, task)
		if err != nil {
			log.Printf(
				"upload handler failed: workflow_id=%s task_id=%s err=%v",
				task.WorkflowInstanceId,
				task.TaskId,
				err,
			)
			return nil, err
		}
		log.Printf(
			"upload handler completed: workflow_id=%s task_id=%s object_key=%s object_path=%s uploaded_at_unix=%d",
			task.WorkflowInstanceId,
			task.TaskId,
			output.ObjectKey,
			output.ObjectPath,
			output.UploadedAtUnix,
		)
		return output, nil
	}
	cleanupHandler := func(task *conductormodel.Task) (any, error) {
		return pipeline.RunCleanupTask(ctx, task)
	}

	if err := taskRunner.StartWorker(
		backup.TaskPgDumpName,
		pgDumpHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		logging.Fatal(fmt.Sprintf("pg_dump worker start error: %v", err))
	}
	if err := taskRunner.StartWorker(
		backup.TaskEncryptName,
		encryptHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		logging.Fatal(fmt.Sprintf("encryption worker start error: %v", err))
	}
	if err := taskRunner.StartWorker(
		backup.TaskCompressName,
		compressHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		logging.Fatal(fmt.Sprintf("compress worker start error: %v", err))
	}
	if err := taskRunner.StartWorker(
		backup.TaskUploadName,
		uploadHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		logging.Fatal(fmt.Sprintf("upload worker start error: %v", err))
	}
	if err := taskRunner.StartWorker(
		backup.TaskCleanupName,
		cleanupHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		logging.Fatal(fmt.Sprintf("cleanup worker start error: %v", err))
	}

	log.Printf(
		"db_backup worker started. tasks=[%s,%s,%s,%s,%s] conductor=%s",
		backup.TaskPgDumpName,
		backup.TaskEncryptName,
		backup.TaskCompressName,
		backup.TaskUploadName,
		backup.TaskCleanupName,
		cfg.ConductorServerURL,
	)

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	<-signals

	taskRunner.Shutdown(backup.TaskPgDumpName)
	taskRunner.Shutdown(backup.TaskEncryptName)
	taskRunner.Shutdown(backup.TaskCompressName)
	taskRunner.Shutdown(backup.TaskUploadName)
	taskRunner.Shutdown(backup.TaskCleanupName)
	taskRunner.WaitWorkers()
}

// initSentry turns Sentry on when a DSN is set. Without SERVICE_NAME, events are tagged db_backup_worker.
func initSentry(sentryDSN string, serviceName string) {
	if strings.TrimSpace(sentryDSN) == "" {
		log.Print("sentry disabled: SENTRY_DSN is empty")
		return
	}
	if strings.TrimSpace(serviceName) == "" {
		serviceName = defaultServiceName
	}
	logging.InitSentry(sentryDSN, serviceName)
}
