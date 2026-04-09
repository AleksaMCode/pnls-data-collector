package main

import (
	"context"
	"db_backup/internal/backup"
	"db_backup/internal/conductor"
	"db_backup/internal/config"
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
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("configuration error: %v", err)
	}

	// Keep SDK config in sync with local config values.
	_ = os.Setenv("CONDUCTOR_SERVER_URL", cfg.ConductorServerURL)
	_ = os.Setenv("TZ", cfg.Timezone)

	ctx := context.Background()
	apiClient := conductorclient.NewAPIClientFromEnv()

	if err := conductor.RegisterAll(ctx, cfg, apiClient); err != nil {
		log.Fatalf("registration error: %v", err)
	}

	uploader, err := storage.NewR2Uploader(cfg)
	if err != nil {
		log.Fatalf("r2 client init error: %v", err)
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
		return pipeline.RunUploadTask(ctx, task)
	}

	if err := taskRunner.StartWorker(
		backup.TaskPgDumpName,
		pgDumpHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		log.Fatalf("pg_dump worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskEncryptName,
		encryptHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		log.Fatalf("encryption worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskCompressName,
		compressHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		log.Fatalf("compress worker start error: %v", err)
	}
	if err := taskRunner.StartWorker(
		backup.TaskUploadName,
		uploadHandler,
		cfg.WorkerCount,
		cfg.PollInterval,
	); err != nil {
		log.Fatalf("upload worker start error: %v", err)
	}

	log.Printf(
		"db_backup worker started. tasks=[%s,%s,%s,%s] conductor=%s",
		backup.TaskPgDumpName,
		backup.TaskEncryptName,
		backup.TaskCompressName,
		backup.TaskUploadName,
		cfg.ConductorServerURL,
	)

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	<-signals

	taskRunner.Shutdown(backup.TaskPgDumpName)
	taskRunner.Shutdown(backup.TaskEncryptName)
	taskRunner.Shutdown(backup.TaskCompressName)
	taskRunner.Shutdown(backup.TaskUploadName)
	taskRunner.WaitWorkers()
}
