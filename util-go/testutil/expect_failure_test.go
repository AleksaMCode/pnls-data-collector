package testutil

import (
	"errors"
	"strings"
	"testing"

	"github.com/AleksaMCode/pnls-data-collector/util-go/internal/testsupport"
)

func requireNoError(t TB, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestExpectFailurePassesWhenTheCheckFails(t *testing.T) {
	ExpectFailure(t, "returns 1 instead of 2", func(t TB) {
		t.Error("expected 2, got 1")
	})
}

func TestExpectFailureFatalStopsTheCheck(t *testing.T) {
	reachedTheEnd := false

	ExpectFailure(t, "returns an error", func(t TB) {
		requireNoError(t, errors.New("connection refused"))
		reachedTheEnd = true
	})

	if reachedTheEnd {
		t.Fatal("the check went on after Fatalf")
	}
}

func TestExpectFailureCountsAPanicAsAFailure(t *testing.T) {
	ExpectFailure(t, "panics on an unknown device", func(TB) {
		panic("unknown device RPI-9")
	})
}

func TestExpectFailureCleanupRunsWithTheTest(t *testing.T) {
	cleaned := false
	t.Run("test", func(t *testing.T) {
		ExpectFailure(t, "known bug", func(t TB) {
			t.Cleanup(func() { cleaned = true })
			t.Error("fails")
		})
	})

	if !cleaned {
		t.Fatal("the check's cleanup did not run")
	}
}

func TestExpectFailureFailsOnceTheBugIsFixed(t *testing.T) {
	if testsupport.InChild(t) {
		ExpectFailure(t, "the fixed bug", func(TB) {})
		return
	}

	result := testsupport.RunInChild(t)

	if result.ExitCode == 0 {
		t.Fatalf("expected the test to fail when the check passes, it passed:\n%s", result.Output())
	}
	for _, want := range []string{"unexpected success", "Known bug: the fixed bug"} {
		if !strings.Contains(result.Output(), want) {
			t.Errorf("expected %q in the output, got:\n%s", want, result.Output())
		}
	}
}
