// Package testutil holds helpers for the tests of util-go and of the services that use it.
package testutil

import (
	"fmt"
	"runtime"
	"strings"
	"sync"
	"testing"
)

// TB is what the check of an ExpectFailure test can use. Failures are recorded instead of failing the test.
type TB interface {
	Helper()
	Name() string
	Log(args ...any)
	Logf(format string, args ...any)
	Error(args ...any)
	Errorf(format string, args ...any)
	Fatal(args ...any)
	Fatalf(format string, args ...any)
	Failed() bool
	Cleanup(f func())
	TempDir() string
	Setenv(key, value string)
}

// ExpectFailure runs a check that asserts the correct behavior of code with a known bug. It passes while the check
// fails, and fails once the check passes, so the test is noticed and turned into a normal test when the bug is fixed.
// It works like unittest.expectedFailure in the Python tests of this repository. A panic in the check counts as a
// failure.
func ExpectFailure(t *testing.T, reason string, check func(t TB)) {
	t.Helper()

	recorder := &failureRecorder{t: t}
	done := make(chan struct{})
	go func() {
		defer close(done)
		defer func() {
			if r := recover(); r != nil {
				recorder.record(fmt.Sprintf("panic: %v", r))
			}
		}()
		check(recorder)
	}()
	<-done

	if !recorder.Failed() {
		t.Fatalf("unexpected success: the known bug seems fixed, replace ExpectFailure with a normal test.\n"+
			"Known bug: %s", reason)
	}
	t.Logf("expected failure. Known bug: %s\n%s", reason, strings.Join(recorder.messages, "\n"))
}

// failureRecorder is passed to the check of ExpectFailure. Fatal stops the check, like it stops a test.
type failureRecorder struct {
	t        *testing.T
	mu       sync.Mutex
	messages []string
}

func (r *failureRecorder) record(message string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.messages = append(r.messages, message)
}

func (r *failureRecorder) Helper()                           {}
func (r *failureRecorder) Name() string                      { return r.t.Name() }
func (r *failureRecorder) Log(args ...any)                   { r.t.Log(args...) }
func (r *failureRecorder) Logf(format string, args ...any)   { r.t.Logf(format, args...) }
func (r *failureRecorder) Error(args ...any)                 { r.record(fmt.Sprint(args...)) }
func (r *failureRecorder) Errorf(format string, args ...any) { r.record(fmt.Sprintf(format, args...)) }
func (r *failureRecorder) Cleanup(f func())                  { r.t.Cleanup(f) }
func (r *failureRecorder) TempDir() string                   { return r.t.TempDir() }
func (r *failureRecorder) Setenv(key, value string)          { r.t.Setenv(key, value) }

func (r *failureRecorder) Fatal(args ...any) {
	r.Error(args...)
	runtime.Goexit()
}

func (r *failureRecorder) Fatalf(format string, args ...any) {
	r.Errorf(format, args...)
	runtime.Goexit()
}

func (r *failureRecorder) Failed() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.messages) > 0
}
