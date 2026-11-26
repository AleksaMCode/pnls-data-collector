package objectstore

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/aws/aws-sdk-go-v2/service/s3/types"
)

func TestR2Endpoint(t *testing.T) {
	if got := R2Endpoint("0123abcd"); got != "https://0123abcd.r2.cloudflarestorage.com" {
		t.Fatalf("R2Endpoint() = %q", got)
	}
}

func TestR2Config(t *testing.T) {
	testCases := []struct {
		name           string
		customEndpoint string
		want           Config
	}{
		{
			name: "Cloudflare R2",
			want: Config{Endpoint: "https://0123abcd.r2.cloudflarestorage.com", Region: R2Region},
		},
		{
			name:           "custom endpoint",
			customEndpoint: "http://localhost:9000",
			want:           Config{Endpoint: "http://localhost:9000", Region: R2Region, UsePathStyle: true},
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			if got := R2Config("0123abcd", testCase.customEndpoint); got != testCase.want {
				t.Fatalf("R2Config() = %+v, want %+v", got, testCase.want)
			}
		})
	}
}

func validConfig() Config {
	cfg := R2Config("0123abcd", "")
	cfg.AccessKey, cfg.SecretKey = "access", "secret"
	cfg.Bucket, cfg.PublicURL = "pnls-backups", "https://pub-backups.r2.dev"
	return cfg
}

func TestNewUsesTheConfig(t *testing.T) {
	testCases := []struct {
		name string
		cfg  Config
	}{
		{name: "Cloudflare R2", cfg: validConfig()},
		{
			name: "local server",
			cfg: func() Config {
				cfg := validConfig()
				cfg.Endpoint, cfg.UsePathStyle = "http://localhost:9000", true
				return cfg
			}(),
		},
		{
			name: "AWS S3",
			cfg: func() Config {
				cfg := validConfig()
				cfg.Endpoint, cfg.Region = "https://s3.eu-central-1.amazonaws.com", "eu-central-1"
				return cfg
			}(),
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			store, err := New(context.Background(), testCase.cfg)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			options := store.client.Options()
			if options.BaseEndpoint == nil || *options.BaseEndpoint != testCase.cfg.Endpoint {
				t.Errorf("BaseEndpoint = %v, want %q", options.BaseEndpoint, testCase.cfg.Endpoint)
			}
			if options.Region != testCase.cfg.Region {
				t.Errorf("Region = %q, want %q", options.Region, testCase.cfg.Region)
			}
			if options.UsePathStyle != testCase.cfg.UsePathStyle {
				t.Errorf("UsePathStyle = %v, want %v", options.UsePathStyle, testCase.cfg.UsePathStyle)
			}
			keys, err := options.Credentials.Retrieve(context.Background())
			if err != nil {
				t.Fatalf("failed to read the keys: %v", err)
			}
			if keys.AccessKeyID != "access" || keys.SecretAccessKey != "secret" {
				t.Errorf("unexpected keys %+v", keys)
			}
			if store.Bucket() != "pnls-backups" {
				t.Errorf("Bucket() = %q", store.Bucket())
			}
		})
	}
}

func TestNewRequiresEndpointRegionAndBucket(t *testing.T) {
	testCases := []struct {
		name    string
		change  func(*Config)
		wantErr string
	}{
		{name: "no endpoint", change: func(c *Config) { c.Endpoint = "" }, wantErr: "endpoint is empty"},
		{name: "no region", change: func(c *Config) { c.Region = "" }, wantErr: "region is empty"},
		{name: "no bucket", change: func(c *Config) { c.Bucket = "" }, wantErr: "bucket is empty"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			cfg := validConfig()
			testCase.change(&cfg)

			store, err := New(context.Background(), cfg)
			if err == nil || !strings.Contains(err.Error(), testCase.wantErr) {
				t.Fatalf("expected an error with %q, got %v", testCase.wantErr, err)
			}
			if store != nil {
				t.Error("expected no store with the error")
			}
		})
	}
}

func TestNewReportsABrokenAWSConfig(t *testing.T) {
	// The SDK reads the usual AWS environment variables, and a profile that doesn't exist is an error.
	t.Setenv("AWS_CONFIG_FILE", filepath.Join(t.TempDir(), "missing-config"))
	t.Setenv("AWS_PROFILE", "missing-profile")

	_, err := New(context.Background(), validConfig())

	if err == nil || !strings.Contains(err.Error(), "failed to load the object store config") {
		t.Fatalf("expected the config error, got %v", err)
	}
}

func TestPublicURL(t *testing.T) {
	for _, publicURL := range []string{"https://pub-backups.r2.dev", "https://pub-backups.r2.dev/"} {
		cfg := validConfig()
		cfg.PublicURL = publicURL
		store, err := New(context.Background(), cfg)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}

		if got := store.PublicURL(
			"db-backup/2026-11-26.sql.gz",
		); got != "https://pub-backups.r2.dev/db-backup/2026-11-26.sql.gz" {
			t.Errorf("PublicURL with the base %q = %q", publicURL, got)
		}
	}
}

// fakeS3 answers PutObject requests like an S3 server with path-style requests, and records them.
type fakeS3 struct {
	server   *httptest.Server
	mu       sync.Mutex
	status   int
	requests []recordedPut
}

type recordedPut struct {
	method, path, contentType, acl, body string
}

func newFakeS3Store(t *testing.T, status int) (*Store, *fakeS3) {
	t.Helper()

	fake := &fakeS3{status: status}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		fake.mu.Lock()
		fake.requests = append(fake.requests, recordedPut{
			method:      r.Method,
			path:        r.URL.Path,
			contentType: r.Header.Get("Content-Type"),
			acl:         r.Header.Get("X-Amz-Acl"),
			body:        string(body),
		})
		fake.mu.Unlock()
		w.WriteHeader(fake.status)
	}))
	t.Cleanup(fake.server.Close)
	t.Setenv("AWS_MAX_ATTEMPTS", "1")

	cfg := R2Config("", fake.server.URL)
	cfg.AccessKey, cfg.SecretKey = "access", "secret"
	cfg.Bucket, cfg.PublicURL = "pnls-charts", "https://pub-charts.r2.dev"
	store, err := New(context.Background(), cfg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	return store, fake
}

func (f *fakeS3) onlyRequest(t *testing.T) recordedPut {
	t.Helper()

	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.requests) != 1 {
		t.Fatalf("expected one request, got %+v", f.requests)
	}
	return f.requests[0]
}

func TestUploadSendsTheObjectWithItsOptions(t *testing.T) {
	store, fake := newFakeS3Store(t, http.StatusOK)

	publicURL, err := store.Upload(context.Background(), "firebase-limit/usage.png", strings.NewReader("png"),
		UploadOptions{ContentType: "image/png", ACL: types.ObjectCannedACLPublicRead})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if publicURL != "https://pub-charts.r2.dev/firebase-limit/usage.png" {
		t.Errorf("publicURL = %q", publicURL)
	}
	request := fake.onlyRequest(t)
	want := recordedPut{
		method:      http.MethodPut,
		path:        "/pnls-charts/firebase-limit/usage.png",
		contentType: "image/png",
		acl:         "public-read",
		body:        "png",
	}
	if request != want {
		t.Fatalf("request = %+v, want %+v", request, want)
	}
}

func TestUploadWithoutOptionsSendsNoACL(t *testing.T) {
	store, fake := newFakeS3Store(t, http.StatusOK)

	if _, err := store.Upload(context.Background(), "key", strings.NewReader("data"), UploadOptions{}); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if acl := fake.onlyRequest(t).acl; acl != "" {
		t.Errorf("expected no ACL header, got %q", acl)
	}
}

func TestUploadReturnsTheStoreError(t *testing.T) {
	store, _ := newFakeS3Store(t, http.StatusForbidden)

	publicURL, err := store.Upload(context.Background(), "db-backup/backup.sql.gz", strings.NewReader("data"),
		UploadOptions{})

	if err == nil {
		t.Fatalf("expected an error, got the link %q", publicURL)
	}
	if publicURL != "" {
		t.Errorf("expected no link with the error, got %q", publicURL)
	}
	if want := "failed to upload db-backup/backup.sql.gz to the bucket pnls-charts"; !strings.Contains(
		err.Error(),
		want,
	) {
		t.Errorf("expected %q in the error, got %v", want, err)
	}
	if strings.Contains(err.Error(), "secret") {
		t.Errorf("the error must not contain the secret key: %v", err)
	}
}

func TestUploadFileStreamsTheFile(t *testing.T) {
	store, fake := newFakeS3Store(t, http.StatusOK)
	path := filepath.Join(t.TempDir(), "backup.sql.gz")
	if err := os.WriteFile(path, []byte("compressed backup"), 0o600); err != nil {
		t.Fatalf("failed to write the file: %v", err)
	}

	publicURL, err := store.UploadFile(context.Background(), "db-backup/backup.sql.gz", path,
		UploadOptions{ContentType: "application/gzip"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if publicURL != "https://pub-charts.r2.dev/db-backup/backup.sql.gz" {
		t.Errorf("publicURL = %q", publicURL)
	}
	request := fake.onlyRequest(t)
	if request.body != "compressed backup" || request.contentType != "application/gzip" {
		t.Errorf("unexpected request %+v", request)
	}
}

func TestUploadFileMissingFile(t *testing.T) {
	store, fake := newFakeS3Store(t, http.StatusOK)
	path := filepath.Join(t.TempDir(), "missing.sql.gz")

	_, err := store.UploadFile(context.Background(), "key", path, UploadOptions{})

	if err == nil || !strings.Contains(err.Error(), "failed to open "+path) {
		t.Fatalf("expected the open error, got %v", err)
	}
	if len(fake.requests) != 0 {
		t.Errorf("expected no request, got %+v", fake.requests)
	}
}
