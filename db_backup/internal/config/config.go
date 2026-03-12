package config

import (
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"strconv"
	"time"

	"github.com/joho/godotenv"
)

const (
	defaultConductorURL      = "http://conductor:8080/api"
	defaultWorkflowName      = "db_backup_workflow"
	defaultWorkflowVersion   = 1
	defaultScheduleName      = "db_backup_daily_2300_paris"
	defaultScheduleCron      = "0 0 23 * * ?"
	defaultWorkerCount       = 2
	defaultPollIntervalMS    = 200
	defaultUploadTimeoutSecs = 120
	defaultWorkDir           = "/tmp/db-backup"
	defaultTimezone          = "Europe/Paris"
	defaultPgDumpBin         = "pg_dump"
)

type Config struct {
	ConductorServerURL string
	WorkflowName       string
	WorkflowVersion    int32
	ScheduleName       string
	ScheduleCron       string
	Timezone           string
	WorkerCount        int
	PollInterval       time.Duration

	PgDumpBin string
	WorkDir   string

	DBHost     string
	DBPort     string
	DBUser     string
	DBPassword string
	DBName     string

	R2AccessKey         string
	R2SecretKey         string
	R2BucketName        string
	R2BucketPublicURL   string
	R2Endpoint          string
	CloudflareAccountID string

	EncryptionKeyRaw string
	UploadTimeout    time.Duration
}

func Load() (Config, error) {
	_ = godotenv.Load()

	cfg := Config{
		ConductorServerURL:  getEnv("CONDUCTOR_SERVER_URL", defaultConductorURL),
		WorkflowName:        getEnv("DB_BACKUP_WORKFLOW_NAME", defaultWorkflowName),
		WorkflowVersion:     int32(getEnvInt("DB_BACKUP_WORKFLOW_VERSION", defaultWorkflowVersion)),
		ScheduleName:        getEnv("DB_BACKUP_SCHEDULE_NAME", defaultScheduleName),
		ScheduleCron:        getEnv("DB_BACKUP_SCHEDULE_CRON", defaultScheduleCron),
		Timezone:            getEnv("DB_BACKUP_TIMEZONE", defaultTimezone),
		WorkerCount:         getEnvInt("DB_BACKUP_WORKER_COUNT", defaultWorkerCount),
		PollInterval:        time.Duration(getEnvInt("DB_BACKUP_POLL_INTERVAL_MS", defaultPollIntervalMS)) * time.Millisecond,
		PgDumpBin:           getEnv("DB_BACKUP_PG_DUMP_BIN", defaultPgDumpBin),
		WorkDir:             getEnv("DB_BACKUP_WORK_DIR", defaultWorkDir),
		DBHost:              os.Getenv("DB_HOST"),
		DBPort:              getEnv("DB_PORT", "5432"),
		DBUser:              os.Getenv("DB_USER"),
		DBPassword:          os.Getenv("DB_PASSWORD"),
		DBName:              os.Getenv("DB_NAME"),
		R2AccessKey:         os.Getenv("R2_ACCESS_KEY"),
		R2SecretKey:         os.Getenv("R2_SECRET_KEY"),
		R2BucketName:        os.Getenv("R2_BUCKET_NAME"),
		R2BucketPublicURL:   os.Getenv("R2_BUCKET_PUBLIC_URL"),
		R2Endpoint:          os.Getenv("R2_ENDPOINT"),
		CloudflareAccountID: os.Getenv("CLOUDFLARE_ACCOUNT_ID"),
		EncryptionKeyRaw:    os.Getenv("DB_BACKUP_ENCRYPTION_KEY"),
		UploadTimeout:       time.Duration(getEnvInt("DB_BACKUP_UPLOAD_TIMEOUT_SECONDS", defaultUploadTimeoutSecs)) * time.Second,
	}

	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func (c Config) Validate() error {
	if c.ConductorServerURL == "" {
		return errors.New("CONDUCTOR_SERVER_URL is required")
	}
	if c.WorkflowName == "" || c.ScheduleName == "" || c.ScheduleCron == "" {
		return errors.New("workflow and scheduler settings cannot be empty")
	}
	if c.WorkerCount < 1 {
		return errors.New("DB_BACKUP_WORKER_COUNT must be >= 1")
	}
	if c.PollInterval <= 0 {
		return errors.New("DB_BACKUP_POLL_INTERVAL_MS must be > 0")
	}
	if c.R2AccessKey == "" || c.R2SecretKey == "" || c.R2BucketName == "" {
		return errors.New("R2_ACCESS_KEY, R2_SECRET_KEY and R2_BUCKET_NAME are required")
	}
	if c.R2BucketPublicURL == "" {
		return errors.New("R2_BUCKET_PUBLIC_URL is required")
	}
	if _, err := c.DecodedEncryptionKey(); err != nil {
		return fmt.Errorf("invalid DB_BACKUP_ENCRYPTION_KEY: %w", err)
	}
	return nil
}

func (c Config) DecodedEncryptionKey() ([]byte, error) {
	if c.EncryptionKeyRaw == "" {
		return nil, errors.New("empty key")
	}

	if b, err := base64.StdEncoding.DecodeString(c.EncryptionKeyRaw); err == nil && len(b) == 32 {
		return b, nil
	}
	if b, err := hex.DecodeString(c.EncryptionKeyRaw); err == nil && len(b) == 32 {
		return b, nil
	}
	if len(c.EncryptionKeyRaw) == 32 {
		return []byte(c.EncryptionKeyRaw), nil
	}

	return nil, errors.New("key must decode to 32 bytes (AES-256)")
}

func getEnv(k string, fallback string) string {
	v := os.Getenv(k)
	if v == "" {
		return fallback
	}
	return v
}

func getEnvInt(k string, fallback int) int {
	v := os.Getenv(k)
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}
