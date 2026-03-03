package common

import (
	"errors"
	"os"
	"os/exec"
	"testing"
	"time"
)

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
