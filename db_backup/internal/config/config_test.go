package config

import (
	"encoding/base64"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
)

func TestDecodedEncryptionKey_Base64(t *testing.T) {
	raw := []byte("12345678901234567890123456789012")
	cfg := Config{
		EncryptionKeyRaw: base64.StdEncoding.EncodeToString(raw),
	}

	key, err := cfg.DecodedEncryptionKey()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(key) != 32 {
		t.Fatalf("expected 32-byte key, got %d", len(key))
	}
}

func TestDecodedEncryptionKey_Invalid(t *testing.T) {
	cfg := Config{
		EncryptionKeyRaw: "invalid",
	}
	if _, err := cfg.DecodedEncryptionKey(); err == nil {
		t.Fatal("expected error for invalid key")
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
