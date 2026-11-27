package main

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func TestProcessDeviceStatusAlertsOnceWhenADeviceGoesOffline(t *testing.T) {
	logs := testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	ctx := context.Background()

	before := time.Now().UTC()
	processDeviceStatus(ctx, DEVICE_RPI_1, true, "Device `RPI-1` is offline")
	first := cachedOffline(t, DEVICE_RPI_1)
	processDeviceStatus(ctx, DEVICE_RPI_1, true, "Device `RPI-1` is offline")

	if messages := texts(webhook); len(messages) != 1 || messages[0] != "Device `RPI-1` is offline" {
		t.Fatalf("expected one alert, got %q", messages)
	}
	if first == nil || first.FirstDiscoveredAt.Before(before) || !first.UpdatedAt.Equal(first.FirstDiscoveredAt) {
		t.Fatalf("unexpected first offline state %+v", first)
	}
	second := cachedOffline(t, DEVICE_RPI_1)
	if !second.FirstDiscoveredAt.Equal(first.FirstDiscoveredAt) || second.UpdatedAt.Before(first.UpdatedAt) {
		t.Errorf("expected the first time kept and the update moved, got %+v after %+v", second, first)
	}
	if !strings.Contains(logs.String(), "Device `RPI-1` is still offline. First seen: ") {
		t.Errorf("expected the second check in the log, got:\n%s", logs.String())
	}
}

func TestProcessDeviceStatusReportsTheRecovery(t *testing.T) {
	testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	ctx := context.Background()
	firstSeen := time.Date(2026, time.November, 27, 9, 0, 0, 0, time.UTC)
	if err := setOfflineDeviceCache(ctx, DEVICE_RPI_2, offlineDeviceCache{
		FirstDiscoveredAt: firstSeen, UpdatedAt: firstSeen.Add(10 * time.Minute),
	}); err != nil {
		t.Fatalf("failed to set the cache: %v", err)
	}

	processDeviceStatus(ctx, DEVICE_RPI_2, false, "")

	want := "Device `RPI-2` is back online. First offline detected at 2026-11-27T09:00:00Z, " +
		"last offline check at 2026-11-27T09:10:00Z"
	if message := webhook.OnlyMessage(t)["text"]; message != want {
		t.Fatalf("message = %q, want %q", message, want)
	}
	if cachedOffline(t, DEVICE_RPI_2) != nil {
		t.Error("expected the offline state to be removed")
	}
}

func TestProcessDeviceStatusOnlineWithoutAnOfflineState(t *testing.T) {
	logs := testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)

	processDeviceStatus(context.Background(), DEVICE_RPI_3, false, "")

	if messages := texts(webhook); len(messages) != 0 {
		t.Fatalf("expected no message, got %q", messages)
	}
	if !strings.Contains(logs.String(), "Device `RPI-3` is online and has no offline cache state") {
		t.Errorf("expected the online state in the log, got:\n%s", logs.String())
	}
}

func TestProcessDeviceStatusTracksDevicesSeparately(t *testing.T) {
	testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	ctx := context.Background()

	processDeviceStatus(ctx, DEVICE_RPI_1, true, "RPI-1 offline")
	processDeviceStatus(ctx, DEVICE_RPI_2, true, "RPI-2 offline")
	processDeviceStatus(ctx, DEVICE_RPI_1, false, "")

	messages := texts(webhook)
	if len(messages) != 3 || !strings.HasPrefix(messages[2], "Device `RPI-1` is back online.") {
		t.Fatalf("unexpected messages %q", messages)
	}
	if cachedOffline(t, DEVICE_RPI_2) == nil {
		t.Error("expected RPI-2 to stay offline")
	}
}

func TestProcessDeviceStatusWhenRedisFailsOnTheRecovery(t *testing.T) {
	logs := testutil.CaptureLog(t)
	redis := useMiniredis(t)
	webhook := useWebhook(t)
	redis.SetError("ERR injected failure")

	processDeviceStatus(context.Background(), DEVICE_RPI_1, false, "")

	if messages := texts(webhook); len(messages) != 0 {
		t.Fatalf("expected no message, got %q", messages)
	}
	if !strings.Contains(logs.String(), "Failed to clear offline status for `RPI-1`") {
		t.Errorf("expected the Redis error in the log, got:\n%s", logs.String())
	}
}

func TestProcessDeviceStatusAlertsWhenRedisFails(t *testing.T) {
	logs := testutil.CaptureLog(t)
	redis := useMiniredis(t)
	webhook := useWebhook(t)
	redis.SetError("ERR injected failure")

	processDeviceStatus(context.Background(), DEVICE_RPI_1, true, "Device `RPI-1` is offline")

	if !strings.Contains(logs.String(), "Failed to cache offline status for `RPI-1`") {
		t.Errorf("expected the Redis error in the log, got:\n%s", logs.String())
	}
	messages := texts(webhook)
	reason := "processDeviceStatus returns without an alert when Redis can't store the offline state, so a Redis " +
		"outage hides every offline device."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if len(messages) != 1 {
			t.Errorf("expected the alert to be sent, got %q", messages)
		}
	})
}

// redisAddressEnv passes the address of the parent's miniredis to the child process.
const redisAddressEnv = "COLLSTATNOT_TEST_REDIS"

func TestOfflineAlertSurvivesAMattermostFailure(t *testing.T) {
	if testutil.InChild(t) {
		REDIS_URL, REDIS_PORT, _ = strings.Cut(os.Getenv(redisAddressEnv), ":")
		REDIS_DB = "0"
		if err := initRedisClient(context.Background()); err != nil {
			t.Fatalf("failed to connect to the parent's Redis: %v", err)
		}
		MATTERMOST_WEBHOOK_URL = testutil.RefusedURL()
		processDeviceStatus(context.Background(), DEVICE_RPI_1, true, "Device `RPI-1` is offline")
		return
	}
	redis := useMiniredis(t)

	// Mattermost can't be reached when the device goes offline, which ends the process.
	result := testutil.RunInChild(t, redisAddressEnv+"="+redis.Addr())
	if result.ExitCode == 0 {
		t.Fatalf("expected the failed delivery to end the process:\n%s", result.Output())
	}

	// After the restart, the device is still offline, and Mattermost answers again.
	testutil.CaptureLog(t)
	webhook := useWebhook(t)
	processDeviceStatus(context.Background(), DEVICE_RPI_1, true, "Device `RPI-1` is offline")

	messages := texts(webhook)
	reason := "the offline state is stored before the alert is sent, and a failed delivery ends the process, so " +
		"after the restart the device counts as already reported and the alert is never sent."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if len(messages) != 1 {
			t.Errorf("expected the alert after the restart, got %q", messages)
		}
	})
}

func TestInitRedisClient(t *testing.T) {
	redis := useMiniredis(t)
	redis.RequireAuth("secret")
	REDIS_PASSWORD, REDIS_DB = "secret", "3"

	if err := initRedisClient(context.Background()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	options := redisClient.Options()
	if options.Addr != redis.Addr() || options.DB != 3 || options.Password != "secret" {
		t.Errorf("unexpected options %s db %d", options.Addr, options.DB)
	}
	if options.DialTimeout != 3*time.Second || options.ReadTimeout != 3*time.Second ||
		options.WriteTimeout != 3*time.Second {
		t.Errorf("unexpected timeouts %+v", options)
	}
}

func TestInitRedisClientDefaults(t *testing.T) {
	useMiniredis(t)
	REDIS_URL, REDIS_PORT, REDIS_DB = "127.0.0.1", "", ""

	// Whether or not something listens on 6379 here, the client is set up for it.
	_ = initRedisClient(context.Background())

	if options := redisClient.Options(); options.Addr != "127.0.0.1:6379" || options.DB != 0 {
		t.Errorf("expected 127.0.0.1:6379 and database 0, got %s and %d", options.Addr, options.DB)
	}
}

func TestInitRedisClientErrors(t *testing.T) {
	testCases := []struct {
		name    string
		change  func()
		wantErr string
	}{
		{name: "no URL", change: func() { REDIS_URL = "" }, wantErr: "REDIS_URL is required"},
		{name: "invalid database", change: func() { REDIS_DB = "two" }, wantErr: "invalid REDIS_DB `two`"},
		{name: "wrong password", change: func() { REDIS_PASSWORD = "wrong" }, wantErr: "failed to connect to Redis"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			redis := useMiniredis(t)
			redis.RequireAuth("secret")
			REDIS_PASSWORD = "secret"
			testCase.change()

			if err := initRedisClient(context.Background()); err == nil ||
				!strings.Contains(err.Error(), testCase.wantErr) {
				t.Fatalf("expected %q, got %v", testCase.wantErr, err)
			}
		})
	}
}

func TestCloseRedisClientWithoutAClient(t *testing.T) {
	original := redisClient
	t.Cleanup(func() { redisClient = original })
	redisClient = nil

	if err := closeRedisClient(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestOfflineCacheErrors(t *testing.T) {
	ctx := context.Background()

	t.Run("broken entry", func(t *testing.T) {
		redis := useMiniredis(t)
		if err := redis.Set(DEVICE_RPI_1, "{not json"); err != nil {
			t.Fatalf("failed to set the entry: %v", err)
		}

		if _, err := getOfflineDeviceCache(ctx, DEVICE_RPI_1); err == nil ||
			!strings.Contains(err.Error(), "failed to decode Redis cache for `RPI-1`") {
			t.Errorf("getOfflineDeviceCache: expected the decode error, got %v", err)
		}
		if _, _, err := markDeviceOffline(ctx, DEVICE_RPI_1, time.Now()); err == nil {
			t.Error("markDeviceOffline: expected the decode error")
		}
		if _, _, err := markDeviceOnline(ctx, DEVICE_RPI_1); err == nil {
			t.Error("markDeviceOnline: expected the decode error")
		}
	})

	t.Run("Redis down", func(t *testing.T) {
		redis := useMiniredis(t)
		redis.Close()

		if _, err := getOfflineDeviceCache(ctx, DEVICE_RPI_1); err == nil ||
			!strings.Contains(err.Error(), "failed to get Redis cache for `RPI-1`") {
			t.Errorf("getOfflineDeviceCache: expected the Redis error, got %v", err)
		}
		if err := setOfflineDeviceCache(ctx, DEVICE_RPI_1, offlineDeviceCache{}); err == nil ||
			!strings.Contains(err.Error(), "failed to set Redis cache for `RPI-1`") {
			t.Errorf("setOfflineDeviceCache: expected the Redis error, got %v", err)
		}
	})

	t.Run("Redis refuses commands", func(t *testing.T) {
		redis := useMiniredis(t)
		redis.SetError("ERR injected failure")

		if _, _, err := markDeviceOffline(ctx, DEVICE_RPI_2, time.Now()); err == nil {
			t.Error("markDeviceOffline: expected the error")
		}
		if _, _, err := markDeviceOnline(ctx, DEVICE_RPI_2); err == nil {
			t.Error("markDeviceOnline: expected the error")
		}
	})
}

func TestMarkDeviceWithAKeyOfAnotherType(t *testing.T) {
	ctx := context.Background()
	redis := useMiniredis(t)
	if _, err := redis.Push(DEVICE_RPI_2, "x"); err != nil {
		t.Fatalf("failed to make a list: %v", err)
	}

	if _, _, err := markDeviceOffline(ctx, DEVICE_RPI_2, time.Now()); err == nil ||
		!strings.Contains(err.Error(), "WRONGTYPE") {
		t.Errorf("markDeviceOffline: expected WRONGTYPE, got %v", err)
	}
	if _, wasOffline, err := markDeviceOnline(ctx, DEVICE_RPI_2); err == nil || wasOffline {
		t.Errorf("markDeviceOnline: expected WRONGTYPE, got %v, %v", wasOffline, err)
	}
}
