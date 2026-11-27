package testutil

import (
	"bytes"
	"errors"
	"os"
	"os/exec"
	"regexp"
	"testing"
)

const childEnv = "UTIL_GO_TEST_CHILD"

// ChildResult is what a test run in a child process printed, and how the process ended.
type ChildResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// Output is everything the child printed. The standard logger writes to stderr unless a test changes it.
func (r ChildResult) Output() string {
	return r.Stdout + r.Stderr
}

// InChild reports whether the test runs in the child process started by RunInChild. Code that ends the process,
// e.g. with log.Fatal or os.Exit, must only run there.
func InChild(t *testing.T) bool {
	t.Helper()
	return os.Getenv(childEnv) == t.Name()
}

// RunInChild runs the current test again in a new process, with the extra environment variables, and returns what it
// printed. It is used for code that ends the process. The test must not be a subtest.
func RunInChild(t *testing.T, env ...string) ChildResult {
	t.Helper()

	//nolint:gosec // G204: the command is this test binary.
	cmd := exec.Command(os.Args[0], "-test.run=^"+regexp.QuoteMeta(t.Name())+"$", "-test.count=1")
	cmd.Env = append(append(os.Environ(), childEnv+"="+t.Name()), env...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	result := ChildResult{Stdout: stdout.String(), Stderr: stderr.String()}
	if exitErr, ok := errors.AsType[*exec.ExitError](err); ok {
		result.ExitCode = exitErr.ExitCode()
	} else if err != nil {
		t.Fatalf("could not run the child process: %v", err)
	}
	return result
}
