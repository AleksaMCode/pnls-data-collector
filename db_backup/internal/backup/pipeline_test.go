package backup

import (
	"bytes"
	"compress/gzip"
	"encoding/base64"
	"io"
	"os"
	"path/filepath"
	"testing"

	"db_backup/internal/config"
)

func TestEncryptAndGzipFile(t *testing.T) {
	tmpDir := t.TempDir()
	inputPath := filepath.Join(tmpDir, "input.sql")
	encPath := filepath.Join(tmpDir, "input.sql.enc")
	gzPath := filepath.Join(tmpDir, "input.sql.enc.gz")

	content := []byte("hello world")
	if err := os.WriteFile(inputPath, content, 0o600); err != nil {
		t.Fatalf("write input file: %v", err)
	}

	cfg := config.Config{
		EncryptionKeyRaw: base64.StdEncoding.EncodeToString([]byte("12345678901234567890123456789012")),
	}

	p := &Pipeline{cfg: cfg}
	if err := p.encryptFile(inputPath, encPath); err != nil {
		t.Fatalf("encrypt file: %v", err)
	}
	if err := gzipFile(encPath, gzPath); err != nil {
		t.Fatalf("gzip file: %v", err)
	}

	gzFile, err := os.Open(gzPath)
	if err != nil {
		t.Fatalf("open gzip file: %v", err)
	}
	defer gzFile.Close()

	gr, err := gzip.NewReader(gzFile)
	if err != nil {
		t.Fatalf("new gzip reader: %v", err)
	}
	defer gr.Close()

	uncompressed, err := io.ReadAll(gr)
	if err != nil {
		t.Fatalf("read gzip: %v", err)
	}
	if bytes.Equal(uncompressed, content) {
		t.Fatal("encrypted payload should not equal plaintext")
	}
}
