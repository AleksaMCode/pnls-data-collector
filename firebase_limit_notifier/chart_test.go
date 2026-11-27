package main

import (
	"bytes"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// pathEnv passes a file path to the child process.
const pathEnv = "FBLIMNOT_TEST_PATH"

func TestGeneratePieChartInMemory(t *testing.T) {
	pieChart, err := generatePieChartInMemory(250, 750)
	if err != nil {
		t.Fatalf("generatePieChartInMemory returned error: %v", err)
	}
	if len(pieChart) == 0 {
		t.Fatal("expected non-empty pie chart bytes")
	}
}

func TestGeneratePieChartInMemoryIsAPNG(t *testing.T) {
	pieChart, err := generatePieChartInMemory(250, 750)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	config, err := png.DecodeConfig(bytes.NewReader(pieChart))
	if err != nil {
		t.Fatalf("expected a PNG, got an error: %v", err)
	}
	if config.Width < 400 || config.Height < 300 {
		t.Fatalf("expected a chart that can be read in Mattermost, got %dx%d", config.Width, config.Height)
	}
}

func TestGeneratePieChartInMemoryEmptyAndFullDatabase(t *testing.T) {
	for _, usage := range []float64{0, FIREBASE_LIMIT_MB} {
		if _, err := generatePieChartInMemory(usage, FIREBASE_LIMIT_MB-usage); err != nil {
			t.Errorf("usage %v MB: unexpected error: %v", usage, err)
		}
	}
}

func TestGeneratePieChartInMemoryRejectsNegativeValues(t *testing.T) {
	pieChart, err := generatePieChartInMemory(1200, -200)

	if err == nil {
		t.Fatalf("expected an error, got %d bytes", len(pieChart))
	}
	if pieChart != nil {
		t.Errorf("expected no chart with the error, got %d bytes", len(pieChart))
	}
}

func TestSaveByteArrayToFile(t *testing.T) {
	tmpDir := t.TempDir()
	target := filepath.Join(tmpDir, "chart.png")
	content := []byte("fake-png-content")

	saveByteArrayToFile(target, content)

	got, err := os.ReadFile(target)
	if err != nil {
		t.Fatalf("failed to read saved file: %v", err)
	}
	if !bytes.Equal(got, content) {
		t.Fatalf("saved content mismatch: got %q, expected %q", string(got), string(content))
	}
}

func TestSaveByteArrayToFileInAMissingFolderFatal(t *testing.T) {
	if testutil.InChild(t) {
		saveByteArrayToFile(os.Getenv(pathEnv), []byte("png"))
		return
	}

	result := testutil.RunInChild(t, pathEnv+"="+filepath.Join(t.TempDir(), "missing", "chart.png"))

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Fatal Error: Failed to save pie chart:") {
		t.Fatalf("expected the failure to be logged, got:\n%s", result.Output())
	}
}
