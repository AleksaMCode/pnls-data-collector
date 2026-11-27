package containers

import (
	"context"
	"io"
	"strconv"
	"sync"
	"testing"

	tc "github.com/testcontainers/testcontainers-go"
	tcexec "github.com/testcontainers/testcontainers-go/exec"
	"github.com/testcontainers/testcontainers-go/wait"
)

const (
	// RedisImage is the cache the services use. Keep it in sync with the redis image in aggregator/docker-compose.yml
	// and REDIS_IMAGE in tests/integration/containers.py.
	RedisImage = "redis:8.8.0"
	// RedisPassword is the password the server requires, as it does in production.
	RedisPassword = "redis-test-password"
	// redisDatabases is the number of logical databases a Redis server has by default.
	redisDatabases = 16
)

// Redis is a running Redis server.
type Redis struct {
	// Host and Port are where the server listens, for REDIS_URL and REDIS_PORT.
	Host string
	Port string

	container tc.Container
	mu        sync.Mutex
	// leased marks the databases tests are using. Database 0 is left to anything that doesn't choose one.
	leased [redisDatabases]bool
}

var redisServer shared[*Redis]

// StartRedis returns the Redis server shared by the tests of this binary, and starts it on first use.
func StartRedis(t *testing.T) *Redis {
	t.Helper()

	return redisServer.get(t, "Redis", func(ctx context.Context) (*Redis, error) {
		container, err := tc.Run(ctx, RedisImage,
			tc.WithCmd("redis-server", "--requirepass", RedisPassword),
			tc.WithExposedPorts("6379/tcp"),
			tc.WithWaitStrategy(wait.ForAll(
				wait.ForLog("Ready to accept connections"),
				wait.ForListeningPort("6379/tcp"),
			)),
		)
		if err != nil {
			return nil, err
		}
		host, err := container.Host(ctx)
		if err != nil {
			return nil, err
		}
		port, err := container.MappedPort(ctx, "6379/tcp")
		if err != nil {
			return nil, err
		}
		return &Redis{Host: host, Port: port.Port(), container: container}, nil
	})
}

// NewDatabase leases a logical database that no running test uses, emptied for the test. The database is released
// when the test ends, after the cleanups the test registered later, such as closing its clients, so a later test can
// lease it again.
func (r *Redis) NewDatabase(t *testing.T) int {
	t.Helper()

	database := r.lease()
	if database == 0 {
		t.Fatalf("all %d Redis databases are leased by running tests", redisDatabases-1)
	}
	t.Cleanup(func() { r.release(database) })

	r.Command(t, database, "FLUSHDB")
	return database
}

// lease marks the lowest free database as used and returns it, or 0 when none is free.
func (r *Redis) lease() int {
	r.mu.Lock()
	defer r.mu.Unlock()

	for database := 1; database < redisDatabases; database++ {
		if !r.leased[database] {
			r.leased[database] = true
			return database
		}
	}
	return 0
}

func (r *Redis) release(database int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.leased[database] = false
}

// Command runs a redis-cli command in a database, inside the container, and returns its output.
func (r *Redis) Command(t *testing.T, database int, args ...string) string {
	t.Helper()

	command := append([]string{
		"redis-cli", "--no-auth-warning", "-a", RedisPassword, "-n", strconv.Itoa(database),
	}, args...)
	code, output, err := r.container.Exec(t.Context(), command, tcexec.Multiplexed())
	if err != nil {
		t.Fatalf("failed to run redis-cli: %v", err)
	}
	printed, _ := io.ReadAll(output)
	if code != 0 {
		t.Fatalf("redis-cli %v failed with exit code %d:\n%s", args, code, printed)
	}
	return string(printed)
}
