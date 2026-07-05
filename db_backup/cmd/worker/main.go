package main

import (
	"context"
	"db_backup/internal/backup"
	"db_backup/internal/conductor"
	"db_backup/internal/config"
	applog "db_backup/internal/logging"
	"db_backup/internal/storage"
	"log"
	"os"
	"os/signal"
	"syscall"

	conductorclient "github.com/conductor-sdk/conductor-go/sdk/client"
	conductormodel "github.com/conductor-sdk/conductor-go/sdk/model"
	"github.com/conductor-sdk/conductor-go/sdk/worker"
)

func main() {
	applog.InitSentry(os.Getenv("SENTRY_DSN"), os.Getenv("SERVICE_NAME"))

	cfg, err := config.Load()
	if err != nil {
		applog.Fatalf("configuration error: %v", err)
	}

	// Keep SDK config in sync with local config values.
	_ = os.Setenv("CONDUCTOR_SERVER_URL", cfg.ConductorServerURL)
	_ = os.Setenv("TZ", cfg.Timezone)

	ctx := context.Background()
	apiClient := conductorclient.NewAPIClientFromEnv()

	if err := conductor.RegisterAll(ctx, cfg, apiClient); err != nil {
		applog.Fatalf("registration error: %v", err)
	}

	uploader, err := storage.NewR2Uploader(cfg)
	if err != nil {
		applog.Fatalf("r2 client init error: %v", err)
	}
	pipeline := backup.NewPipeline(cfg, uploader)

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
		applog.Fatalf("pg_dump worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskEncryptName,
		encryptHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		applog.Fatalf("encryption worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskCompressName,
		compressHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		applog.Fatalf("compress worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskUploadName,
		uploadHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		applog.Fatalf("upload worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskCleanupName,
		cleanupHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		applog.Fatalf("cleanup worker start error: %v", err)
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
