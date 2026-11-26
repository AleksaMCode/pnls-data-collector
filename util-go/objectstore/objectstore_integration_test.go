//go:build integration

package objectstore_test

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/aws/smithy-go"

	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil/containers"
)

// siloStore returns a store on a new bucket of the shared Silo server, with the config changed by change.
func siloStore(t *testing.T, change func(*objectstore.Config)) (*objectstore.Store, *containers.Silo) {
	t.Helper()

	silo := containers.StartSilo(t)
	cfg := objectstore.R2Config("", silo.Endpoint)
	cfg.AccessKey, cfg.SecretKey = containers.SiloAccessKey, containers.SiloSecretKey
	cfg.Bucket, cfg.PublicURL = silo.CreateBucket(t, "objectstore"), "https://pub-test.r2.dev"
	if change != nil {
		change(&cfg)
	}

	store, err := objectstore.New(context.Background(), cfg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	return store, silo
}

func TestUploadStoresTheObject(t *testing.T) {
	store, silo := siloStore(t, nil)

	publicURL, err := store.Upload(t.Context(), "firebase-limit/usage.png", strings.NewReader("png"),
		objectstore.UploadOptions{ContentType: "image/png"})
	if err != nil {
		t.Fatalf("failed to upload: %v", err)
	}

	if publicURL != "https://pub-test.r2.dev/firebase-limit/usage.png" {
		t.Errorf("publicURL = %q", publicURL)
	}
	content, contentType := silo.GetObject(t, store.Bucket(), "firebase-limit/usage.png")
	if string(content) != "png" || contentType != "image/png" {
		t.Fatalf("got %q (%s)", content, contentType)
	}
}

func TestUploadFileStoresTheFile(t *testing.T) {
	store, silo := siloStore(t, nil)
	path := filepath.Join(t.TempDir(), "backup.sql.gz")
	if err := os.WriteFile(path, []byte("compressed backup"), 0o600); err != nil {
		t.Fatalf("failed to write the file: %v", err)
	}

	if _, err := store.UploadFile(t.Context(), "db-backup/backup.sql.gz", path,
		objectstore.UploadOptions{ContentType: "application/gzip"}); err != nil {
		t.Fatalf("failed to upload: %v", err)
	}

	content, contentType := silo.GetObject(t, store.Bucket(), "db-backup/backup.sql.gz")
	if string(content) != "compressed backup" || contentType != "application/gzip" {
		t.Fatalf("got %q (%s)", content, contentType)
	}
}

func TestUploadWithWrongKeys(t *testing.T) {
	store, _ := siloStore(t, func(cfg *objectstore.Config) { cfg.SecretKey = "wrong-secret" })

	_, err := store.Upload(t.Context(), "backup.sql.gz", strings.NewReader("data"), objectstore.UploadOptions{})

	if apiErr, ok := errors.AsType[smithy.APIError](err); !ok || apiErr.ErrorCode() != "SignatureDoesNotMatch" {
		t.Fatalf("expected SignatureDoesNotMatch, got %v", err)
	}
}

func TestUploadToAMissingBucket(t *testing.T) {
	store, _ := siloStore(t, func(cfg *objectstore.Config) { cfg.Bucket = "objectstore-missing" })

	_, err := store.Upload(t.Context(), "backup.sql.gz", strings.NewReader("data"), objectstore.UploadOptions{})

	if apiErr, ok := errors.AsType[smithy.APIError](err); !ok || apiErr.ErrorCode() != "NoSuchBucket" {
		t.Fatalf("expected NoSuchBucket, got %v", err)
	}
}

func TestUploadWithoutPathStyleCantReachALocalServer(t *testing.T) {
	t.Setenv("AWS_MAX_ATTEMPTS", "1")
	store, _ := siloStore(t, func(cfg *objectstore.Config) { cfg.UsePathStyle = false })

	// The bucket goes into the host name, <bucket>.localhost, which the local server doesn't answer for.
	if _, err := store.Upload(t.Context(), "backup.sql.gz", strings.NewReader("data"),
		objectstore.UploadOptions{}); err == nil {
		t.Fatal("expected the upload to fail without path-style requests")
	}
}
