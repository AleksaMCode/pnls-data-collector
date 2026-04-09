package common

import (
	"errors"
	"os"
	"os/exec"
	"testing"
	"time"
)

func almostEqual(a float64, b float64, tolerance float64) bool {
	if a > b {
		return a-b < tolerance
	}
	return b-a < tolerance
}

func TestGetTimeNowReturnsRequestedTimezone(t *testing.T) {
	now := GetTimeNow("Europe/Paris")

	loc, err := time.LoadLocation("Europe/Paris")
	if err != nil {
		t.Fatalf("failed to load timezone in test: %v", err)
	}

	if now.Location().String() != loc.String() {
		t.Fatalf("expected location %q, got %q", loc.String(), now.Location().String())
	}
}

func TestGetTimeNowInvalidTimezoneFatal(t *testing.T) {
	if os.Getenv("TEST_INVALID_TZ_FATAL") == "1" {
		GetTimeNow("Invalid/Timezone")
		return
	}

	cmd := exec.Command(os.Args[0], "-test.run=TestGetTimeNowInvalidTimezoneFatal")
	cmd.Env = append(os.Environ(), "TEST_INVALID_TZ_FATAL=1")

	err := cmd.Run()
	if err == nil {
		t.Fatal("expected process to exit with non-zero status")
	}

	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		t.Fatalf("expected *exec.ExitError, got %T (%v)", err, err)
	}
}

func TestGetPercentage(t *testing.T) {
	tests := []struct {
		name     string
		part     float64
		whole    float64
		expected float64
	}{
		{"normal case", 50, 200, 25},
		{"half", 1, 2, 50},
		{"zero part", 0, 100, 0},
		{"decimal", 2.5, 10, 25},
		{"zero whole", 1, 0, 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := GetPercentage(tt.part, tt.whole)
			if !almostEqual(result, tt.expected, 0.000001) {
				t.Errorf("expected %f, got %f", tt.expected, result)
			}
		})
	}
}
