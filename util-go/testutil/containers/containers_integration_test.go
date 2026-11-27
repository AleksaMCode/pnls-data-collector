//go:build integration

package containers

import (
	"bytes"
	"context"
	"strconv"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
)

func TestSiloStoresObjectsInTheTestsBucket(t *testing.T) {
	silo := StartSilo(t)
	bucket := silo.CreateBucket(t, "containers-test")

	_, err := silo.S3Client(t).PutObject(t.Context(), &s3.PutObjectInput{
		Bucket:      &bucket,
		Key:         aws.String("charts/usage.png"),
		Body:        bytes.NewReader([]byte("png")),
		ContentType: aws.String("image/png"),
	})
	if err != nil {
		t.Fatalf("failed to upload: %v", err)
	}

	content, contentType := silo.GetObject(t, bucket, "charts/usage.png")
	if string(content) != "png" || contentType != "image/png" {
		t.Fatalf("got %q (%s), want %q (image/png)", content, contentType, "png")
	}
	if keys := silo.ListKeys(t, bucket); len(keys) != 1 || keys[0] != "charts/usage.png" {
		t.Fatalf("unexpected keys %v", keys)
	}
}

func TestSiloIsSharedButBucketsAreNot(t *testing.T) {
	first, second := StartSilo(t), StartSilo(t)
	if first != second {
		t.Fatal("expected one Silo server for the test binary")
	}
	if a, b := first.CreateBucket(t, "same"), first.CreateBucket(t, "same"); a == b {
		t.Fatalf("expected two buckets, got %s twice", a)
	}
}

func TestFirebaseEmulatorServesTheServicesClient(t *testing.T) {
	database := StartFirebaseEmulator(t).CreateDatabase(t, "containers-test")
	database.Set(t, "/RPI-1-2026-06-14", map[string]any{"status": map[string]any{"online": true}})

	// The services make their client with util-go, from a credentials file and the database URL.
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(t), database.URL())

	var node map[string]map[string]bool
	if err := client.NewRef("RPI-1-2026-06-14").Get(t.Context(), &node); err != nil {
		t.Fatalf("failed to read through the SDK: %v", err)
	}
	if !node["status"]["online"] {
		t.Fatalf("unexpected node %v", node)
	}

	if err := client.NewRef("RPI-2-2026-06-14").Set(t.Context(), map[string]int{"devices": 3}); err != nil {
		t.Fatalf("failed to write through the SDK: %v", err)
	}
	var written map[string]int
	database.Get(t, "RPI-2-2026-06-14", &written)
	if written["devices"] != 3 {
		t.Fatalf("unexpected node %v", written)
	}
}

func TestFirebaseDatabasesAreSeparate(t *testing.T) {
	emulator := StartFirebaseEmulator(t)
	first, second := emulator.CreateDatabase(t, "same"), emulator.CreateDatabase(t, "same")

	first.Set(t, "stats", map[string]int{"count": 1})

	var stats any
	second.Get(t, "stats", &stats)
	if stats != nil {
		t.Fatalf("expected the second database to be empty, got %v", stats)
	}
}

func TestPostgresRunsSQLInTheTestsDatabase(t *testing.T) {
	server := StartPostgres(t)
	database := server.CreateDatabase(t, "containers_test")

	server.Exec(t, database, "CREATE TABLE people (name TEXT); INSERT INTO people VALUES ('Alice'), ('Bob');")

	// psql exits with an error, which fails the test, unless the rows are in this database.
	server.Exec(t, database, `DO $$ BEGIN
		IF (SELECT count(*) FROM people) <> 2 THEN RAISE EXCEPTION 'expected two rows'; END IF;
	END $$;`)
}

func TestPostgresIsSharedButDatabasesAreNot(t *testing.T) {
	first, second := StartPostgres(t), StartPostgres(t)
	if first != second {
		t.Fatal("expected one Postgres server for the test binary")
	}
	if first.Host == "" || first.Port == "" {
		t.Fatalf("expected the server's address, got %+v", first)
	}
	if a, b := first.CreateDatabase(t, "same"), first.CreateDatabase(t, "same"); a == b {
		t.Fatalf("expected two databases, got %s twice", a)
	}
}

func TestRedisStoresKeysInTheTestsDatabase(t *testing.T) {
	server := StartRedis(t)
	database := server.NewDatabase(t)

	if reply := server.Command(t, database, "SET", "RPI-1", "offline"); !strings.Contains(reply, "OK") {
		t.Fatalf("SET answered %q", reply)
	}
	if reply := server.Command(t, database, "GET", "RPI-1"); strings.TrimSpace(reply) != "offline" {
		t.Fatalf("GET answered %q", reply)
	}
}

func TestRedisIsSharedButDatabasesAreNot(t *testing.T) {
	first, second := StartRedis(t), StartRedis(t)
	if first != second {
		t.Fatal("expected one Redis server for the test binary")
	}
	a, b := first.NewDatabase(t), first.NewDatabase(t)
	if a == b || a == 0 || b == 0 {
		t.Fatalf("expected two databases other than 0, got %d and %d", a, b)
	}

	first.Command(t, a, "SET", "RPI-1", "offline")
	if reply := first.Command(t, b, "EXISTS", "RPI-1"); strings.TrimSpace(reply) != "0" {
		t.Fatalf("expected the key only in database %d, EXISTS in %d answered %q", a, b, reply)
	}
}

func TestRedisReleasesDatabasesWhenTestsEnd(t *testing.T) {
	server := StartRedis(t)
	held := server.NewDatabase(t)

	// More tests than Redis has databases, one after another, each with a database of its own while it runs.
	var leased []int
	for i := range redisDatabases + 4 {
		t.Run(strconv.Itoa(i), func(t *testing.T) {
			database := server.NewDatabase(t)
			if database == held {
				t.Fatalf("got database %d, which the parent test still holds", held)
			}
			// The previous test left a key here, which the lease emptied.
			if reply := server.Command(t, database, "EXISTS", "RPI-1"); strings.TrimSpace(reply) != "0" {
				t.Fatalf("expected an empty database %d, EXISTS answered %q", database, reply)
			}
			server.Command(t, database, "SET", "RPI-1", "offline")
			leased = append(leased, database)
		})
	}

	if len(leased) != redisDatabases+4 || leased[0] != leased[len(leased)-1] {
		t.Fatalf("expected the released database to be leased again, got %v", leased)
	}
}
