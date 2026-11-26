package containers

import (
	"context"
	"io"
	"testing"

	tcexec "github.com/testcontainers/testcontainers-go/exec"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
)

const (
	// PostgresImage is the database the services back up and write to. Keep it in sync with the postgres image in
	// aggregator/docker-compose.yml and POSTGRES_IMAGE in tests/integration/containers.py.
	PostgresImage = "postgres:16"
	// PostgresUser and PostgresPassword are the superuser the tests connect as.
	PostgresUser     = "postgres"
	PostgresPassword = "postgres"
)

// Postgres is a running Postgres server.
type Postgres struct {
	// Host and Port are where the server listens, for DB_HOST and DB_PORT.
	Host string
	Port string

	container *postgres.PostgresContainer
}

var postgresServer shared[*Postgres]

// StartPostgres returns the Postgres server shared by the tests of this binary, and starts it on first use.
func StartPostgres(t *testing.T) *Postgres {
	t.Helper()

	return postgresServer.get(t, "Postgres", func(ctx context.Context) (*Postgres, error) {
		container, err := postgres.Run(ctx, PostgresImage,
			postgres.WithUsername(PostgresUser),
			postgres.WithPassword(PostgresPassword),
			postgres.BasicWaitStrategies(),
		)
		if err != nil {
			return nil, err
		}
		host, err := container.Host(ctx)
		if err != nil {
			return nil, err
		}
		port, err := container.MappedPort(ctx, "5432/tcp")
		if err != nil {
			return nil, err
		}
		return &Postgres{Host: host, Port: port.Port(), container: container}, nil
	})
}

// CreateDatabase creates a new empty database named after the prefix, and returns its name.
func (p *Postgres) CreateDatabase(t *testing.T, prefix string) string {
	t.Helper()

	name := prefix + "_" + randomSuffix(t)
	p.Exec(t, PostgresUser, "CREATE DATABASE "+name)
	return name
}

// Exec runs SQL statements in a database with psql inside the container, so the tests need no database driver.
func (p *Postgres) Exec(t *testing.T, database, sql string) {
	t.Helper()

	code, output, err := p.container.Exec(t.Context(), []string{
		"psql", "-v", "ON_ERROR_STOP=1", "--username", PostgresUser, "--dbname", database, "--command", sql,
	}, tcexec.Multiplexed())
	if err != nil {
		t.Fatalf("failed to run psql: %v", err)
	}
	if code != 0 {
		printed, _ := io.ReadAll(output)
		t.Fatalf("psql failed with exit code %d in %s:\n%s", code, database, printed)
	}
}
