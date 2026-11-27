// Package containers starts the Docker containers shared by the integration tests of the Go services, like
// tests/integration/containers.py does for the Python services. Each container starts once per test binary, on first
// use, and is removed by the testcontainers reaper when the binary ends. Tests share a container but get their own
// bucket or database, so they never see each other's data.
package containers

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"testing"

	tc "github.com/testcontainers/testcontainers-go"
)

// shared starts a container once per test binary and keeps the result, or the error, for the tests that follow.
type shared[T any] struct {
	once  sync.Once
	value T
	err   error
}

func (s *shared[T]) get(t *testing.T, name string, start func(ctx context.Context) (T, error)) T {
	t.Helper()

	requireDocker(t)
	s.once.Do(func() { s.value, s.err = start(context.Background()) })
	if s.err != nil {
		t.Fatalf("failed to start %s: %v", name, s.err)
	}
	return s.value
}

// requireDocker skips the test when Docker can't be reached, e.g. on a laptop without Docker or with rootless Docker
// on Windows. In CI the test fails instead, so a broken Docker setup is never hidden by skipped tests.
func requireDocker(t *testing.T) {
	t.Helper()

	if err := dockerHealth(); err != nil {
		if os.Getenv("CI") != "" {
			t.Fatalf("Docker is required for the integration tests in CI: %v", err)
		}
		t.Skipf("Docker is not available, skipping the integration test: %v", err)
	}
}

func dockerHealth() (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("%v", r)
		}
	}()

	provider, err := tc.ProviderDefault.GetProvider()
	if err != nil {
		return err
	}
	defer provider.Close()
	return provider.Health(context.Background())
}

// repoRoot is the root of this repository, found from this file, so the tests can build images from its folders.
func repoRoot() string {
	_, file, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(file), "..", "..", "..")
}
