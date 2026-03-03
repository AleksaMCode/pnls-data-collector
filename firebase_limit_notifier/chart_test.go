package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestGeneratePieChartInMemory(t *testing.T) {
	pieChart, err := generatePieChartInMemory(250, 750)
	if err != nil {
		t.Fatalf("generatePieChartInMemory returned error: %v", err)
	}
	if len(pieChart) == 0 {
		t.Fatal("expected non-empty pie chart bytes")
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
	if string(got) != string(content) {
		t.Fatalf("saved content mismatch: got %q, expected %q", string(got), string(content))
	}
}
