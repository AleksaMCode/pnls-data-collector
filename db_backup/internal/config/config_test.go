package config

import (
	"encoding/base64"
	"testing"
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
