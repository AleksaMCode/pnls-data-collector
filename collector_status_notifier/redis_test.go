package main

import (
	"context"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
)

func TestOfflineCacheLifecycle(t *testing.T) {
	mockRedis, err := miniredis.Run()
	if err != nil {
		t.Fatalf("failed to start miniredis: %v", err)
	}
	t.Cleanup(mockRedis.Close)

	REDIS_URL = mockRedis.Host()
	REDIS_PORT = mockRedis.Port()
	REDIS_PASSWORD = ""
	REDIS_DB = "0"

	ctx := context.Background()
	if err := initRedisClient(ctx); err != nil {
		t.Fatalf("initRedisClient() returned error: %v", err)
	}
	t.Cleanup(func() {
		if err := closeRedisClient(); err != nil {
			t.Fatalf("closeRedisClient() returned error: %v", err)
		}
	})

	firstSeen := time.Now().UTC().Add(-5 * time.Minute)
	isFirstOffline, firstCache, err := markDeviceOffline(ctx, DEVICE_RPI_1, firstSeen)
	if err != nil {
		t.Fatalf("markDeviceOffline() first call returned error: %v", err)
	}
	if !isFirstOffline {
		t.Fatalf("expected first markDeviceOffline() call to be first offline")
	}
	if !firstCache.FirstDiscoveredAt.Equal(firstSeen) || !firstCache.UpdatedAt.Equal(firstSeen) {
		t.Fatalf("unexpected first cache value: %+v", firstCache)
	}

	secondSeen := firstSeen.Add(2 * time.Minute)
	isFirstOffline, secondCache, err := markDeviceOffline(ctx, DEVICE_RPI_1, secondSeen)
	if err != nil {
		t.Fatalf("markDeviceOffline() second call returned error: %v", err)
	}
	if isFirstOffline {
		t.Fatalf("expected second markDeviceOffline() call not to be first offline")
	}
	if !secondCache.FirstDiscoveredAt.Equal(firstSeen) {
		t.Fatalf("expected FirstDiscoveredAt to remain %s, got %s", firstSeen, secondCache.FirstDiscoveredAt)
	}
	if !secondCache.UpdatedAt.Equal(secondSeen) {
		t.Fatalf("expected UpdatedAt to become %s, got %s", secondSeen, secondCache.UpdatedAt)
	}

	cached, err := getOfflineDeviceCache(ctx, DEVICE_RPI_1)
	if err != nil {
		t.Fatalf("getOfflineDeviceCache() returned error: %v", err)
	}
	if cached == nil {
		t.Fatal("expected cached device status to exist")
	}

	previousCache, wasOffline, err := markDeviceOnline(ctx, DEVICE_RPI_1)
	if err != nil {
		t.Fatalf("markDeviceOnline() returned error: %v", err)
	}
	if !wasOffline {
		t.Fatal("expected markDeviceOnline() to report previous offline state")
	}
	if previousCache == nil {
		t.Fatal("expected previous cache to be returned")
	}

	cached, err = getOfflineDeviceCache(ctx, DEVICE_RPI_1)
	if err != nil {
		t.Fatalf("getOfflineDeviceCache() after online returned error: %v", err)
	}
	if cached != nil {
		t.Fatalf("expected cache to be removed after online transition, got %+v", cached)
	}
}
