package config

import (
	"bytes"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// testKey is a valid AES-256 key, as the 32 characters themselves.
const testKey = "12345678901234567890123456789012"

// variables are the environment variables Load reads.
var variables = []string{
	"CONDUCTOR_SERVER_URL", "DB_BACKUP_WORKFLOW_NAME", "DB_BACKUP_WORKFLOW_VERSION", "DB_BACKUP_SCHEDULE_NAME",
	"DB_BACKUP_SCHEDULE_CRON", "DB_BACKUP_TIMEZONE", "DB_BACKUP_WORKER_COUNT", "DB_BACKUP_POLL_INTERVAL_MS",
	"DB_BACKUP_PG_DUMP_BIN", "DB_BACKUP_WORK_DIR", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME",
	"R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET_NAME", "R2_BUCKET_PUBLIC_URL", "R2_ENDPOINT",
	"CLOUDFLARE_ACCOUNT_ID", "DB_BACKUP_ENCRYPTION_KEY", "DB_BACKUP_UPLOAD_TIMEOUT_SECONDS", "SENTRY_DSN",
	"SERVICE_NAME",
}

// cleanEnv removes the variables from the environment, and moves to an empty folder so no .env file is read, until
// the test ends.
func cleanEnv(t *testing.T) {
	t.Helper()

	for _, name := range variables {
		t.Setenv(name, "")
		if err := os.Unsetenv(name); err != nil {
			t.Fatalf("failed to unset %s: %v", name, err)
		}
	}
	t.Chdir(t.TempDir())
}

// setEnv sets the variables until the test ends.
func setEnv(t *testing.T, values map[string]string) {
	t.Helper()

	for name, value := range values {
		t.Setenv(name, value)
	}
}

// requiredEnv are the variables Load can't do without.
func requiredEnv() map[string]string {
	return map[string]string{
		"R2_ACCESS_KEY":            "access",
		"R2_SECRET_KEY":            "secret",
		"R2_BUCKET_NAME":           "pnls-backups",
		"R2_BUCKET_PUBLIC_URL":     "https://pub-backups.r2.dev",
		"DB_BACKUP_ENCRYPTION_KEY": testKey,
	}
}

// validConfig is a config that passes Validate.
func validConfig() Config {
	return Config{
		ConductorServerURL: defaultConductorURL,
		WorkflowName:       defaultWorkflowName,
		ScheduleName:       defaultScheduleName,
		ScheduleCron:       defaultScheduleCron,
		WorkerCount:        1,
		PollInterval:       time.Second,
		DBHost:             "postgres",
		DBPort:             "5432",
		DBUser:             "backup",
		DBName:             "app",
		R2AccessKey:        "access",
		R2SecretKey:        "secret",
		R2BucketName:       "pnls-backups",
		R2BucketPublicURL:  "https://pub-backups.r2.dev",
		EncryptionKeyRaw:   testKey,
	}
}

func TestLoadDefaults(t *testing.T) {
	cleanEnv(t)
	setEnv(t, requiredEnv())

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	want := Config{
		ConductorServerURL: "http://conductor:8080/api",
		WorkflowName:       "db_backup_workflow",
		WorkflowVersion:    1,
		ScheduleName:       "db_backup_daily_2300_paris",
		ScheduleCron:       "0 0 23 * * ?",
		Timezone:           "Europe/Paris",
		WorkerCount:        2,
		PollInterval:       200 * time.Millisecond,
		PgDumpBin:          "pg_dump",
		WorkDir:            "/tmp/db-backup",
		DBPort:             "5432",
		R2AccessKey:        "access",
		R2SecretKey:        "secret",
		R2BucketName:       "pnls-backups",
		R2BucketPublicURL:  "https://pub-backups.r2.dev",
		EncryptionKeyRaw:   testKey,
		UploadTimeout:      120 * time.Second,
		ServiceName:        "db_backup_worker",
	}
	if cfg != want {
		t.Fatalf("Load() =\n%+v\nwant\n%+v", cfg, want)
	}
}

func TestLoadReadsEveryVariable(t *testing.T) {
	cleanEnv(t)
	setEnv(t, map[string]string{
		"CONDUCTOR_SERVER_URL":             "http://localhost:8080/api",
		"DB_BACKUP_WORKFLOW_NAME":          "backup",
		"DB_BACKUP_WORKFLOW_VERSION":       "3",
		"DB_BACKUP_SCHEDULE_NAME":          "nightly",
		"DB_BACKUP_SCHEDULE_CRON":          "0 0 1 * * ?",
		"DB_BACKUP_TIMEZONE":               "UTC",
		"DB_BACKUP_WORKER_COUNT":           "4",
		"DB_BACKUP_POLL_INTERVAL_MS":       "50",
		"DB_BACKUP_PG_DUMP_BIN":            "/usr/bin/pg_dump",
		"DB_BACKUP_WORK_DIR":               "/var/backups",
		"DB_HOST":                          "postgres",
		"DB_PORT":                          "6543",
		"DB_USER":                          "backup",
		"DB_PASSWORD":                      "password",
		"DB_NAME":                          "app",
		"R2_ACCESS_KEY":                    "access",
		"R2_SECRET_KEY":                    "secret",
		"R2_BUCKET_NAME":                   "pnls-backups",
		"R2_BUCKET_PUBLIC_URL":             "https://pub-backups.r2.dev",
		"R2_ENDPOINT":                      "http://localhost:9000",
		"CLOUDFLARE_ACCOUNT_ID":            "0123abcd",
		"DB_BACKUP_ENCRYPTION_KEY":         testKey,
		"DB_BACKUP_UPLOAD_TIMEOUT_SECONDS": "900",
		"SENTRY_DSN":                       "https://key@sentry.example.com/1",
		"SERVICE_NAME":                     "db_backup",
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	want := Config{
		ConductorServerURL:  "http://localhost:8080/api",
		WorkflowName:        "backup",
		WorkflowVersion:     3,
		ScheduleName:        "nightly",
		ScheduleCron:        "0 0 1 * * ?",
		Timezone:            "UTC",
		WorkerCount:         4,
		PollInterval:        50 * time.Millisecond,
		PgDumpBin:           "/usr/bin/pg_dump",
		WorkDir:             "/var/backups",
		DBHost:              "postgres",
		DBPort:              "6543",
		DBUser:              "backup",
		DBPassword:          "password",
		DBName:              "app",
		R2AccessKey:         "access",
		R2SecretKey:         "secret",
		R2BucketName:        "pnls-backups",
		R2BucketPublicURL:   "https://pub-backups.r2.dev",
		R2Endpoint:          "http://localhost:9000",
		CloudflareAccountID: "0123abcd",
		EncryptionKeyRaw:    testKey,
		UploadTimeout:       900 * time.Second,
		SentryDSN:           "https://key@sentry.example.com/1",
		ServiceName:         "db_backup",
	}
	if cfg != want {
		t.Fatalf("Load() =\n%+v\nwant\n%+v", cfg, want)
	}
}

func TestLoadReadsTheEnvFile(t *testing.T) {
	cleanEnv(t)
	var content strings.Builder
	for name, value := range requiredEnv() {
		fmt.Fprintf(&content, "%s=%s\n", name, value)
	}
	content.WriteString("DB_HOST=postgres\n")
	if err := os.WriteFile(filepath.Join(".", ".env"), []byte(content.String()), 0o600); err != nil {
		t.Fatalf("failed to write the .env file: %v", err)
	}
	// godotenv doesn't load these variables into the environment of this test, so remove them when it ends.
	t.Cleanup(func() {
		for name := range requiredEnv() {
			_ = os.Unsetenv(name)
		}
		_ = os.Unsetenv("DB_HOST")
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.DBHost != "postgres" || cfg.R2BucketName != "pnls-backups" {
		t.Fatalf("expected the values of the .env file, got %+v", cfg)
	}
}

func TestLoadDoesNotReplaceTheEnvironmentWithTheEnvFile(t *testing.T) {
	cleanEnv(t)
	setEnv(t, requiredEnv())
	t.Setenv("DB_HOST", "from-the-environment")
	if err := os.WriteFile(".env", []byte("DB_HOST=from-the-file\n"), 0o600); err != nil {
		t.Fatalf("failed to write the .env file: %v", err)
	}

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.DBHost != "from-the-environment" {
		t.Fatalf("DBHost = %q, want the environment's value", cfg.DBHost)
	}
}

func TestLoadFallsBackOnInvalidNumbers(t *testing.T) {
	// This is the current behaviour: a number that doesn't parse is replaced by its default without a warning.
	cleanEnv(t)
	setEnv(t, requiredEnv())
	setEnv(t, map[string]string{
		"DB_BACKUP_WORKFLOW_VERSION":       "one",
		"DB_BACKUP_WORKER_COUNT":           "2.5",
		"DB_BACKUP_POLL_INTERVAL_MS":       "fast",
		"DB_BACKUP_UPLOAD_TIMEOUT_SECONDS": "15m",
	})

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.WorkflowVersion != 1 || cfg.WorkerCount != 2 || cfg.PollInterval != 200*time.Millisecond ||
		cfg.UploadTimeout != 120*time.Second {
		t.Fatalf("expected the defaults, got %+v", cfg)
	}
}

func TestLoadReturnsTheValidationError(t *testing.T) {
	cleanEnv(t)
	setEnv(t, requiredEnv())
	t.Setenv("DB_BACKUP_WORKER_COUNT", "0")

	cfg, err := Load()

	if err == nil || err.Error() != "DB_BACKUP_WORKER_COUNT must be >= 1" {
		t.Fatalf("expected the worker count error, got %v", err)
	}
	if cfg != (Config{}) {
		t.Errorf("expected an empty config with the error, got %+v", cfg)
	}
}

func TestValidate(t *testing.T) {
	testCases := []struct {
		name    string
		change  func(*Config)
		wantErr string
	}{
		{name: "valid", change: func(*Config) {}},
		{
			name:    "no Conductor URL",
			change:  func(c *Config) { c.ConductorServerURL = "" },
			wantErr: "CONDUCTOR_SERVER_URL is required",
		},
		{
			name:    "no workflow name",
			change:  func(c *Config) { c.WorkflowName = "" },
			wantErr: "workflow and scheduler settings cannot be empty",
		},
		{
			name:    "no schedule name",
			change:  func(c *Config) { c.ScheduleName = "" },
			wantErr: "workflow and scheduler settings cannot be empty",
		},
		{
			name:    "no schedule cron",
			change:  func(c *Config) { c.ScheduleCron = "" },
			wantErr: "workflow and scheduler settings cannot be empty",
		},
		{
			name:    "no workers",
			change:  func(c *Config) { c.WorkerCount = 0 },
			wantErr: "DB_BACKUP_WORKER_COUNT must be >= 1",
		},
		{
			name:    "no poll interval",
			change:  func(c *Config) { c.PollInterval = 0 },
			wantErr: "DB_BACKUP_POLL_INTERVAL_MS must be > 0",
		},
		{
			name:    "negative poll interval",
			change:  func(c *Config) { c.PollInterval = -time.Millisecond },
			wantErr: "DB_BACKUP_POLL_INTERVAL_MS must be > 0",
		},
		{
			name:    "no access key",
			change:  func(c *Config) { c.R2AccessKey = "" },
			wantErr: "R2_ACCESS_KEY, R2_SECRET_KEY and R2_BUCKET_NAME are required",
		},
		{
			name:    "no secret key",
			change:  func(c *Config) { c.R2SecretKey = "" },
			wantErr: "R2_ACCESS_KEY, R2_SECRET_KEY and R2_BUCKET_NAME are required",
		},
		{
			name:    "no bucket",
			change:  func(c *Config) { c.R2BucketName = "" },
			wantErr: "R2_ACCESS_KEY, R2_SECRET_KEY and R2_BUCKET_NAME are required",
		},
		{
			name:    "no public URL",
			change:  func(c *Config) { c.R2BucketPublicURL = "" },
			wantErr: "R2_BUCKET_PUBLIC_URL is required",
		},
		{
			name:    "no encryption key",
			change:  func(c *Config) { c.EncryptionKeyRaw = "" },
			wantErr: "invalid DB_BACKUP_ENCRYPTION_KEY: empty key",
		},
		{
			name:    "short encryption key",
			change:  func(c *Config) { c.EncryptionKeyRaw = "short" },
			wantErr: "invalid DB_BACKUP_ENCRYPTION_KEY: key must decode to 32 bytes (AES-256)",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			cfg := validConfig()
			testCase.change(&cfg)

			err := cfg.Validate()

			switch {
			case testCase.wantErr == "" && err != nil:
				t.Fatalf("unexpected error: %v", err)
			case testCase.wantErr != "" && (err == nil || err.Error() != testCase.wantErr):
				t.Fatalf("error = %v, want %q", err, testCase.wantErr)
			}
		})
	}
}

func TestValidateRequiresTheDatabaseAndTheStoreAccount(t *testing.T) {
	testCases := []struct {
		name     string
		variable string
		change   func(*Config)
	}{
		{name: "no database host", variable: "DB_HOST", change: func(c *Config) { c.DBHost = "" }},
		{name: "no database user", variable: "DB_USER", change: func(c *Config) { c.DBUser = "" }},
		{name: "no database name", variable: "DB_NAME", change: func(c *Config) { c.DBName = "" }},
		{
			name:     "no account or endpoint",
			variable: "CLOUDFLARE_ACCOUNT_ID",
			change:   func(c *Config) { c.CloudflareAccountID, c.R2Endpoint = "", "" },
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			cfg := validConfig()
			cfg.CloudflareAccountID = "0123abcd"
			testCase.change(&cfg)

			reason := "Validate doesn't check the database settings or the R2 account, so pg_dump or the upload fails " +
				"at backup time instead of at startup."
			testutil.ExpectFailure(t, reason, func(t testutil.TB) {
				if err := cfg.Validate(); err == nil || !strings.Contains(err.Error(), testCase.variable) {
					t.Errorf("expected an error naming %s, got %v", testCase.variable, err)
				}
			})
		})
	}
}

func TestDecodedEncryptionKey(t *testing.T) {
	raw := []byte(testKey)
	binary := make([]byte, 32)
	for i := range binary {
		binary[i] = byte(255 - i)
	}

	testCases := []struct {
		name string
		key  string
		want []byte
	}{
		{name: "base64", key: base64.StdEncoding.EncodeToString(binary), want: binary},
		{name: "hex", key: hex.EncodeToString(binary), want: binary},
		{name: "upper-case hex", key: strings.ToUpper(hex.EncodeToString(binary)), want: binary},
		{name: "32 characters", key: testKey, want: raw},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			key, err := Config{EncryptionKeyRaw: testCase.key}.DecodedEncryptionKey()
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !bytes.Equal(key, testCase.want) {
				t.Fatalf("key = %x, want %x", key, testCase.want)
			}
		})
	}
}

func TestDecodedEncryptionKeyRejectsOtherLengths(t *testing.T) {
	testCases := []struct {
		name    string
		key     string
		wantErr string
	}{
		{name: "empty", key: "", wantErr: "empty key"},
		{name: "short text", key: "invalid", wantErr: "key must decode to 32 bytes (AES-256)"},
		{name: "33 characters", key: testKey + "3", wantErr: "key must decode to 32 bytes (AES-256)"},
		{
			name:    "base64 of 16 bytes",
			key:     base64.StdEncoding.EncodeToString(make([]byte, 16)),
			wantErr: "key must decode to 32 bytes (AES-256)",
		},
		{
			name:    "hex of 31 bytes",
			key:     hex.EncodeToString(make([]byte, 31)),
			wantErr: "key must decode to 32 bytes (AES-256)",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			key, err := Config{EncryptionKeyRaw: testCase.key}.DecodedEncryptionKey()
			if err == nil || err.Error() != testCase.wantErr {
				t.Fatalf("error = %v, want %q", err, testCase.wantErr)
			}
			if key != nil {
				t.Errorf("expected no key with the error, got %x", key)
			}
		})
	}
}

func TestObjectStoreIsTheR2Bucket(t *testing.T) {
	cfg := Config{
		R2AccessKey:         "access",
		R2SecretKey:         "secret",
		R2BucketName:        "pnls-backups",
		R2BucketPublicURL:   "https://pub-backups.r2.dev",
		CloudflareAccountID: "0123abcd",
	}

	want := objectstore.Config{
		Endpoint:  "https://0123abcd.r2.cloudflarestorage.com",
		AccessKey: "access",
		SecretKey: "secret",
		Region:    objectstore.R2Region,
		Bucket:    "pnls-backups",
		PublicURL: "https://pub-backups.r2.dev",
	}
	if got := cfg.ObjectStore(); got != want {
		t.Fatalf("ObjectStore() = %+v, want %+v", got, want)
	}
}

func TestObjectStoreWithACustomEndpoint(t *testing.T) {
	cfg := Config{R2Endpoint: "http://localhost:9000", CloudflareAccountID: "0123abcd"}

	got := cfg.ObjectStore()

	if got.Endpoint != "http://localhost:9000" || !got.UsePathStyle {
		t.Fatalf("expected the custom endpoint with path-style requests, got %+v", got)
	}
}
