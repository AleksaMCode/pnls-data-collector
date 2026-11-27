//go:build integration

package main

import (
	"context"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/firebase"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil/containers"
)

// useRedisContainer connects the service to a new database of the shared Redis server until the test ends.
func useRedisContainer(t *testing.T) (*containers.Redis, int) {
	t.Helper()

	server := containers.StartRedis(t)
	database := server.NewDatabase(t)
	restoreConfig(t)
	REDIS_URL, REDIS_PORT = server.Host, server.Port
	REDIS_PASSWORD, REDIS_DB = containers.RedisPassword, strconv.Itoa(database)
	if err := initRedisClient(context.Background()); err != nil {
		t.Fatalf("failed to connect to Redis: %v", err)
	}
	t.Cleanup(func() {
		_ = closeRedisClient()
		redisClient = nil
	})
	return server, database
}

func TestChecksFallBackToFirebaseAndRememberOfflineDevices(t *testing.T) {
	testutil.CaptureLog(t)
	database := containers.StartFirebaseEmulator(t).CreateDatabase(t, "collector-status")
	redis, redisDB := useRedisContainer(t)
	webhook := useWebhook(t)
	kuma := useFakeKuma(t)
	// Datadog isn't configured, so every check uses Firebase.
	restoreConfig(t)
	DATADOG_API_KEY = ""

	now := parisNow(t)
	stale := now.Add(-30 * time.Minute)
	database.Set(t, "/"+statusNode(DEVICE_RPI_1, now), status(now.Add(-time.Minute)))
	database.Set(t, "/"+statusNode(DEVICE_RPI_2, now), status(stale))
	client := firebase.GetFirebaseClient(context.Background(), database.CredentialsFile(t), database.URL())
	ctx := context.Background()

	checkDevicesStatus(ctx, client)

	want := []string{
		"Device `RPI-2` hasn't been updated in the last 11m0s! Last update: " + stale.Format(TIMESTAMP_FORMAT),
		"Device `RPI-3` has no status for today (" + now.Format("2006-01-02") + ")",
	}
	if got := texts(webhook); !slices.Equal(got, want) {
		t.Fatalf("alerts after the first check =\n%q\nwant\n%q", got, want)
	}
	for device, wantCached := range map[string]string{DEVICE_RPI_1: "0", DEVICE_RPI_2: "1", DEVICE_RPI_3: "1"} {
		if got := strings.TrimSpace(redis.Command(t, redisDB, "EXISTS", device)); got != wantCached {
			t.Errorf("EXISTS %s = %s, want %s", device, got, wantCached)
		}
	}

	// RPI-2 writes a new heartbeat; RPI-3 is still missing.
	database.Set(t, "/"+statusNode(DEVICE_RPI_2, now), status(parisNow(t)))
	checkDevicesStatus(ctx, client)

	messages := texts(webhook)
	if len(messages) != 3 ||
		!strings.HasPrefix(messages[2], "Device `RPI-2` is back online. First offline detected at ") {
		t.Fatalf("expected only RPI-2's recovery after the second check, got %q", messages)
	}
	if got := strings.TrimSpace(redis.Command(t, redisDB, "EXISTS", DEVICE_RPI_2)); got != "0" {
		t.Errorf("expected RPI-2's offline state to be removed, EXISTS answered %s", got)
	}
	if kuma.count() != 2 {
		t.Errorf("Kuma pushes = %d, want one per check", kuma.count())
	}
}
