package backup

import (
	"compress/gzip"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"db_backup/internal/config"
	localmodel "db_backup/internal/model"
	"db_backup/internal/storage"

	conductormodel "github.com/conductor-sdk/conductor-go/sdk/model"
)

const (
	TaskPgDumpName   = "pg_dump_task"
	TaskEncryptName  = "encryption_task"
	TaskCompressName = "compress_task"
	TaskUploadName   = "upload_to_r2_task"
)

type Pipeline struct {
	cfg      config.Config
	uploader storage.ObjectUploader
}

func NewPipeline(cfg config.Config, uploader storage.ObjectUploader) *Pipeline {
	return &Pipeline{
		cfg:      cfg,
		uploader: uploader,
	}
}

func (p *Pipeline) RunPgDumpTask(ctx context.Context, task *conductormodel.Task) (localmodel.PgDumpTaskOutput, error) {
	taskID := strings.TrimSpace(task.TaskId)
	workflowID := strings.TrimSpace(task.WorkflowInstanceId)
	if taskID == "" || workflowID == "" {
		return localmodel.PgDumpTaskOutput{}, conductormodel.NewNonRetryableError(errors.New("missing task id or workflow id"))
	}

	loc, err := time.LoadLocation(p.cfg.Timezone)
	if err != nil {
		return localmodel.PgDumpTaskOutput{}, conductormodel.NewNonRetryableError(fmt.Errorf("invalid timezone: %w", err))
	}
	now := time.Now().In(loc)
	timestamp := now.Format("20060102T150405")
	baseDir := filepath.Join(p.cfg.WorkDir, workflowID)

	if err := os.MkdirAll(baseDir, 0o700); err != nil {
		return localmodel.PgDumpTaskOutput{}, err
	}
	dumpPath := filepath.Join(baseDir, "backup.sql")
	if err := p.runPgDump(ctx, dumpPath); err != nil {
		return localmodel.PgDumpTaskOutput{}, err
	}

	return localmodel.PgDumpTaskOutput{
		TimestampUnix: now.Unix(),
		Timestamp:     timestamp,
		WorkflowID:    workflowID,
		BaseDir:       baseDir,
		DumpPath:      dumpPath,
		DumpFileName:  filepath.Base(dumpPath),
	}, nil
}

func (p *Pipeline) RunEncryptTask(_ context.Context, task *conductormodel.Task) (localmodel.EncryptTaskOutput, error) {
	dumpPath, err := requiredInput(task, "dump_path")
	if err != nil {
		return localmodel.EncryptTaskOutput{}, err
	}
	baseDir, err := requiredInput(task, "base_dir")
	if err != nil {
		return localmodel.EncryptTaskOutput{}, err
	}
	timestamp, err := requiredInput(task, "timestamp")
	if err != nil {
		return localmodel.EncryptTaskOutput{}, err
	}
	dumpFileName, err := requiredInput(task, "dump_file_name")
	if err != nil {
		return localmodel.EncryptTaskOutput{}, err
	}

	encPath := filepath.Join(baseDir, "backup.sql.enc")
	if err := p.encryptFile(dumpPath, encPath); err != nil {
		return localmodel.EncryptTaskOutput{}, err
	}

	return localmodel.EncryptTaskOutput{
		Timestamp:         timestamp,
		WorkflowID:        task.WorkflowInstanceId,
		BaseDir:           baseDir,
		EncryptedPath:     encPath,
		EncryptedFileName: filepath.Base(encPath),
		DumpFileName:      dumpFileName,
	}, nil
}

func (p *Pipeline) RunCompressTask(_ context.Context, task *conductormodel.Task) (localmodel.CompressTaskOutput, error) {
	encPath, err := requiredInput(task, "encrypted_path")
	if err != nil {
		return localmodel.CompressTaskOutput{}, err
	}
	baseDir, err := requiredInput(task, "base_dir")
	if err != nil {
		return localmodel.CompressTaskOutput{}, err
	}
	timestamp, err := requiredInput(task, "timestamp")
	if err != nil {
		return localmodel.CompressTaskOutput{}, err
	}

	gzipPath := filepath.Join(baseDir, "backup.sql.enc.gz")
	if err := gzipFile(encPath, gzipPath); err != nil {
		return localmodel.CompressTaskOutput{}, err
	}

	return localmodel.CompressTaskOutput{
		Timestamp:          timestamp,
		WorkflowID:         task.WorkflowInstanceId,
		BaseDir:            baseDir,
		CompressedPath:     gzipPath,
		CompressedFileName: filepath.Base(gzipPath),
	}, nil
}

func (p *Pipeline) RunUploadTask(ctx context.Context, task *conductormodel.Task) (localmodel.UploadTaskOutput, error) {
	gzipPath, err := requiredInput(task, "compressed_path")
	if err != nil {
		return localmodel.UploadTaskOutput{}, err
	}
	timestamp, err := requiredInput(task, "timestamp")
	if err != nil {
		return localmodel.UploadTaskOutput{}, err
	}
	_, err = requiredInput(task, "base_dir")
	if err != nil {
		return localmodel.UploadTaskOutput{}, err
	}
	dumpFileName, _ := optionalInput(task, "dump_file_name")
	encFileName, _ := optionalInput(task, "encrypted_file_name")
	compressedFileName, _ := optionalInput(task, "compressed_file_name")

	objectKey := fmt.Sprintf("db-backup/%s/%s-%s.sql.enc.gz", timestamp, task.WorkflowInstanceId, task.TaskId)
	uploadCtx, cancel := context.WithTimeout(ctx, p.cfg.UploadTimeout)
	defer cancel()

	objectPath, err := p.uploader.UploadFile(uploadCtx, objectKey, gzipPath)
	if err != nil {
		return localmodel.UploadTaskOutput{}, err
	}

	// _ = os.RemoveAll(baseDir)
	nowUnix := time.Now().Unix()
	return localmodel.UploadTaskOutput{
		ObjectKey:      objectKey,
		ObjectPath:     objectPath,
		WorkflowID:     task.WorkflowInstanceId,
		TaskID:         task.TaskId,
		DumpFileName:   dumpFileName,
		EncryptedName:  encFileName,
		CompressedName: compressedFileName,
		UploadedAtUnix: nowUnix,
	}, nil
}

func (p *Pipeline) runPgDump(ctx context.Context, dumpPath string) error {
	args := []string{"--file", dumpPath, "--format=plain", "--no-owner", "--no-privileges"}

	args = append(args,
		"--host", p.cfg.DBHost,
		"--port", p.cfg.DBPort,
		"--username", p.cfg.DBUser,
		"--dbname", p.cfg.DBName,
	)

	cmd := exec.CommandContext(ctx, p.cfg.PgDumpBin, args...)
	cmd.Env = append(os.Environ(), "PGPASSWORD="+p.cfg.DBPassword)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("pg_dump failed: %w (%s)", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func (p *Pipeline) encryptFile(inputPath string, outputPath string) error {
	key, err := p.cfg.DecodedEncryptionKey()
	if err != nil {
		return conductormodel.NewNonRetryableError(err)
	}
	plaintext, err := os.ReadFile(inputPath)
	if err != nil {
		return err
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return conductormodel.NewNonRetryableError(err)
	}

	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return conductormodel.NewNonRetryableError(err)
	}
	nonce := make([]byte, aesGCM.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return err
	}
	ciphertext := aesGCM.Seal(nil, nonce, plaintext, nil)
	out := append(nonce, ciphertext...)

	if err := os.WriteFile(outputPath, out, 0o600); err != nil {
		return err
	}
	return nil
}

func gzipFile(inputPath string, outputPath string) error {
	inputFile, err := os.Open(inputPath)
	if err != nil {
		return err
	}
	defer inputFile.Close()

	outFile, err := os.OpenFile(outputPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	defer outFile.Close()

	gz := gzip.NewWriter(outFile)
	if _, err := io.Copy(gz, inputFile); err != nil {
		_ = gz.Close()
		return err
	}
	return gz.Close()
}

func requiredInput(task *conductormodel.Task, key string) (string, error) {
	v, ok := task.InputData[key]
	if !ok {
		return "", conductormodel.NewNonRetryableError(fmt.Errorf("missing required input key: %s", key))
	}
	s := strings.TrimSpace(fmt.Sprintf("%v", v))
	if s == "" || s == "<nil>" {
		return "", conductormodel.NewNonRetryableError(fmt.Errorf("empty required input key: %s", key))
	}
	return s, nil
}

func optionalInput(task *conductormodel.Task, key string) (string, bool) {
	v, ok := task.InputData[key]
	if !ok {
		return "", false
	}
	s := strings.TrimSpace(fmt.Sprintf("%v", v))
	if s == "" || s == "<nil>" {
		return "", false
	}
	return s, true
}

func EncodeKeyBase64(raw []byte) string {
	return base64.StdEncoding.EncodeToString(raw)
}
