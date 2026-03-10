//go:build integration

package backup

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"encoding/base64"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"db_backup/internal/conductor"
	"db_backup/internal/config"
	"db_backup/internal/storage"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	conductorclient "github.com/conductor-sdk/conductor-go/sdk/client"
	_jsii "github.com/conductor-sdk/conductor-go/sdk/model"
	"github.com/conductor-sdk/conductor-go/sdk/worker"
	workflowexecutor "github.com/conductor-sdk/conductor-go/sdk/workflow/executor"
	tc "github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/minio"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
)

func TestWorkflowIntegration_PostgresToMinioR2(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			panicMsg := fmt.Sprint(r)
			if strings.Contains(strings.ToLower(panicMsg), "rootless docker is not supported on windows") {
				t.Skipf("skipping integration test due to unsupported Docker mode on Windows: %s", panicMsg)
			}
			panic(r)
		}
	}()

	ctx := context.Background()
	moduleRoot := moduleRootPath(t)

	pgContainer, err := postgres.Run(
		ctx,
		"postgres:16-alpine",
		postgres.WithDatabase("backupdb"),
		postgres.WithUsername("backup"),
		postgres.WithPassword("backup"),
		postgres.WithInitScripts(filepath.Join(moduleRoot, "testdata", "db_backup_seed.sql")),
	)
	if err != nil {
		t.Fatalf("start postgres container: %v", err)
	}
	t.Cleanup(func() {
		_ = pgContainer.Terminate(context.Background())
	})

	dbDSN, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("postgres connection string: %v", err)
	}
	pgDumpBin := resolvePgDumpBinaryForTest(t, pgContainer.GetContainerID())

	minioContainer, err := minio.Run(
		ctx,
		"minio/minio:latest",
		minio.WithUsername("minioadmin"),
		minio.WithPassword("minioadmin"),
		tc.WithWaitStrategy(wait.ForHTTP("/minio/health/live").WithPort("9000/tcp")),
	)
	if err != nil {
		t.Fatalf("start minio container: %v", err)
	}
	t.Cleanup(func() {
		_ = minioContainer.Terminate(context.Background())
	})

	minioEndpoint, err := minioContainer.ConnectionString(ctx)
	if err != nil {
		t.Fatalf("minio connection string: %v", err)
	}
	minioEndpoint = ensureHTTPURL(minioEndpoint)
	if _, err := url.ParseRequestURI(minioEndpoint); err != nil {
		t.Fatalf("invalid minio endpoint %q: %v", minioEndpoint, err)
	}

	minioS3Client, err := newS3ClientForMinio(minioEndpoint, "minioadmin", "minioadmin")
	if err != nil {
		t.Fatalf("minio s3 client: %v", err)
	}
	bucketName := "db-backup-it"
	_, err = minioS3Client.CreateBucket(ctx, &s3.CreateBucketInput{
		Bucket: aws.String(bucketName),
	})
	if err != nil {
		t.Fatalf("create minio bucket: %v", err)
	}

	conductorCtr, err := tc.Run(
		ctx,
		"orkes/conductor-standalone:latest",
		tc.WithExposedPorts("8080/tcp"),
		tc.WithWaitStrategy(wait.ForHTTP("/health").WithPort("8080/tcp").WithStartupTimeout(2*time.Minute)),
	)
	if err != nil {
		t.Fatalf("start conductor container: %v", err)
	}
	t.Cleanup(func() {
		_ = conductorCtr.Terminate(context.Background())
	})

	conductorBaseURL, err := conductorCtr.PortEndpoint(ctx, "8080/tcp", "http")
	if err != nil {
		t.Fatalf("conductor endpoint: %v", err)
	}

	cfg := config.Config{
		ConductorServerURL:  conductorBaseURL + "/api",
		WorkflowName:        "db_backup_workflow",
		WorkflowVersion:     1,
		ScheduleName:        "db_backup_daily_2300_paris",
		ScheduleCron:        "0 0 23 * * ?",
		Timezone:            "Europe/Paris",
		WorkerCount:         2,
		PollInterval:        100 * time.Millisecond,
		PgDumpBin:           pgDumpBin,
		WorkDir:             filepath.Join(moduleRoot, "tmp", "integration"),
		DBDSN:               dbDSN,
		R2AccessKey:         "minioadmin",
		R2SecretKey:         "minioadmin",
		R2BucketName:        bucketName,
		R2BucketPublicURL:   minioEndpoint,
		R2Endpoint:          minioEndpoint,
		CloudflareAccountID: "local",
		EncryptionKeyRaw:    base64.StdEncoding.EncodeToString([]byte("12345678901234567890123456789012")),
		UploadTimeout:       30 * time.Second,
	}
	if err := cfg.Validate(); err != nil {
		t.Fatalf("config validation failed: %v", err)
	}

	if err := os.Chdir(moduleRoot); err != nil {
		t.Fatalf("chdir module root: %v", err)
	}

	t.Setenv("CONDUCTOR_SERVER_URL", cfg.ConductorServerURL)
	apiClient := conductorclient.NewAPIClientFromEnv()
	if err := conductor.RegisterAll(ctx, cfg, apiClient); err != nil {
		t.Fatalf("register workflow/task/schedule: %v", err)
	}

	uploader, err := storage.NewR2Uploader(cfg)
	if err != nil {
		t.Fatalf("new R2 uploader: %v", err)
	}
	pipeline := NewPipeline(cfg, uploader)

	taskRunner := worker.NewTaskRunnerWithApiClient(apiClient)
	if err := taskRunner.StartWorker(TaskPgDumpName, func(tk *_jsii.Task) (interface{}, error) {
		return pipeline.RunPgDumpTask(ctx, tk)
	}, cfg.WorkerCount, cfg.PollInterval); err != nil {
		t.Fatalf("start pg_dump worker: %v", err)
	}
	if err := taskRunner.StartWorker(TaskEncryptName, func(tk *_jsii.Task) (interface{}, error) {
		return pipeline.RunEncryptTask(ctx, tk)
	}, cfg.WorkerCount, cfg.PollInterval); err != nil {
		t.Fatalf("start encrypt worker: %v", err)
	}
	if err := taskRunner.StartWorker(TaskCompressName, func(tk *_jsii.Task) (interface{}, error) {
		return pipeline.RunCompressTask(ctx, tk)
	}, cfg.WorkerCount, cfg.PollInterval); err != nil {
		t.Fatalf("start compress worker: %v", err)
	}
	if err := taskRunner.StartWorker(TaskUploadName, func(tk *_jsii.Task) (interface{}, error) {
		return pipeline.RunUploadTask(ctx, tk)
	}, cfg.WorkerCount, cfg.PollInterval); err != nil {
		t.Fatalf("start upload worker: %v", err)
	}
	defer func() {
		taskRunner.Shutdown(TaskPgDumpName)
		taskRunner.Shutdown(TaskEncryptName)
		taskRunner.Shutdown(TaskCompressName)
		taskRunner.Shutdown(TaskUploadName)
		taskRunner.WaitWorkers()
	}()

	executor := workflowexecutor.NewWorkflowExecutor(apiClient)
	workflowID, err := executor.StartWorkflow(&_jsii.StartWorkflowRequest{
		Name:    cfg.WorkflowName,
		Version: cfg.WorkflowVersion,
		Input:   map[string]interface{}{},
	})
	if err != nil {
		t.Fatalf("start workflow: %v", err)
	}

	monitor, err := executor.MonitorExecution(workflowID)
	if err != nil {
		t.Fatalf("monitor workflow: %v", err)
	}

	finalWf, err := workflowexecutor.WaitForWorkflowCompletionUntilTimeout(monitor, 2*time.Minute)
	if err != nil {
		t.Fatalf("wait workflow completion: %v", err)
	}
	if !finalWf.IsCompleted() {
		t.Fatalf("workflow did not complete successfully: status=%s reason=%s", finalWf.Status, finalWf.ReasonForIncompletion)
	}

	objectKey, ok := finalWf.Output["object_key"].(string)
	if !ok || objectKey == "" {
		t.Fatalf("workflow output object_key missing: %#v", finalWf.Output)
	}

	obj, err := minioS3Client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(objectKey),
	})
	if err != nil {
		t.Fatalf("get object from minio: %v", err)
	}
	defer obj.Body.Close()

	uploadedBytes, err := io.ReadAll(obj.Body)
	if err != nil {
		t.Fatalf("read uploaded object: %v", err)
	}

	decompressed, err := ungzipBytes(uploadedBytes)
	if err != nil {
		t.Fatalf("gunzip uploaded object: %v", err)
	}

	key, _ := cfg.DecodedEncryptionKey()
	decryptedSQL, err := decryptAESGCM(decompressed, key)
	if err != nil {
		t.Fatalf("decrypt uploaded artifact: %v", err)
	}

	sqlDump := string(decryptedSQL)
	if !strings.Contains(sqlDump, "people") {
		t.Fatalf("expected table name not found in SQL dump")
	}
	if !strings.Contains(strings.ToLower(sqlDump), "alice") {
		t.Fatalf("expected seeded row value not found in SQL dump")
	}
}

func resolvePgDumpBinaryForTest(t *testing.T, postgresContainerID string) string {
	t.Helper()
	if _, err := exec.LookPath("pg_dump"); err == nil {
		return "pg_dump"
	}

	if _, err := exec.LookPath("docker"); err != nil {
		t.Skipf("neither pg_dump nor docker binary available on host: %v", err)
	}

	tempDir := t.TempDir()
	if runtime.GOOS == "windows" {
		wrapperPath := filepath.Join(tempDir, "pg_dump_wrapper.cmd")
		content := fmt.Sprintf("@echo off\r\ndocker exec -i %s pg_dump %%*\r\n", postgresContainerID)
		if err := os.WriteFile(wrapperPath, []byte(content), 0o700); err != nil {
			t.Fatalf("write pg_dump wrapper cmd: %v", err)
		}
		return wrapperPath
	}

	wrapperPath := filepath.Join(tempDir, "pg_dump_wrapper.sh")
	content := fmt.Sprintf("#!/usr/bin/env sh\ndocker exec -i %s pg_dump \"$@\"\n", postgresContainerID)
	if err := os.WriteFile(wrapperPath, []byte(content), 0o700); err != nil {
		t.Fatalf("write pg_dump wrapper script: %v", err)
	}
	return wrapperPath
}

func moduleRootPath(t *testing.T) string {
	t.Helper()
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot resolve caller path")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(filename), "..", ".."))
}

func ensureHTTPURL(raw string) string {
	if strings.HasPrefix(raw, "http://") || strings.HasPrefix(raw, "https://") {
		return raw
	}
	return "http://" + raw
}

func newS3ClientForMinio(endpoint, accessKey, secretKey string) (*s3.Client, error) {
	awsCfg, err := awsconfig.LoadDefaultConfig(
		context.Background(),
		awsconfig.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKey, secretKey, "")),
		awsconfig.WithRegion("us-east-1"),
	)
	if err != nil {
		return nil, err
	}
	return s3.NewFromConfig(awsCfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(endpoint)
		o.UsePathStyle = true
	}), nil
}

func ungzipBytes(data []byte) ([]byte, error) {
	reader, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	defer reader.Close()
	return io.ReadAll(reader)
}

func decryptAESGCM(encrypted []byte, key []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	nonceSize := gcm.NonceSize()
	if len(encrypted) < nonceSize {
		return nil, fmt.Errorf("encrypted payload too short")
	}
	nonce := encrypted[:nonceSize]
	ciphertext := encrypted[nonceSize:]
	return gcm.Open(nil, nonce, ciphertext, nil)
}
