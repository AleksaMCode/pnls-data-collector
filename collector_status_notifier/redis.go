package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

var redisClient *redis.Client

type offlineDeviceCache struct {
	FirstDiscoveredAt time.Time `json:"first_discovered_at"`
	UpdatedAt         time.Time `json:"updated_at"`
}

func initRedisClient(ctx context.Context) error {
	if REDIS_URL == "" {
		return errors.New("REDIS_URL is required")
	}

	port := REDIS_PORT
	if port == "" {
		port = "6379"
	}

	db := 0
	if REDIS_DB != "" {
		parsedDB, err := strconv.Atoi(REDIS_DB)
		if err != nil {
			return fmt.Errorf("invalid REDIS_DB `%s`: %w", REDIS_DB, err)
		}
		db = parsedDB
	}

	redisClient = redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%s", REDIS_URL, port),
		Password:     REDIS_PASSWORD,
		DB:           db,
		DialTimeout:  3 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
	})

	if err := redisClient.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return nil
}

func closeRedisClient() error {
	if redisClient == nil {
		return nil
	}
	return redisClient.Close()
}

func getOfflineDeviceCache(ctx context.Context, device string) (*offlineDeviceCache, error) {
	payload, err := redisClient.Get(ctx, device).Result()
	if errors.Is(err, redis.Nil) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get Redis cache for `%s`: %w", device, err)
	}

	var cached offlineDeviceCache
	if err := json.Unmarshal([]byte(payload), &cached); err != nil {
		return nil, fmt.Errorf("failed to decode Redis cache for `%s`: %w", device, err)
	}

	return &cached, nil
}

func setOfflineDeviceCache(ctx context.Context, device string, value offlineDeviceCache) error {
	payload, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to encode Redis cache for `%s`: %w", device, err)
	}

	if err := redisClient.Set(ctx, device, payload, 0).Err(); err != nil {
		return fmt.Errorf("failed to set Redis cache for `%s`: %w", device, err)
	}

	return nil
}

func markDeviceOffline(ctx context.Context, device string, observedAt time.Time) (bool, *offlineDeviceCache, error) {
	existing, err := getOfflineDeviceCache(ctx, device)
	if err != nil {
		return false, nil, err
	}

	if existing == nil {
		cached := offlineDeviceCache{
			FirstDiscoveredAt: observedAt,
			UpdatedAt:         observedAt,
		}
		if err := setOfflineDeviceCache(ctx, device, cached); err != nil {
			return false, nil, err
		}
		return true, &cached, nil
	}

	existing.UpdatedAt = observedAt
	if err := setOfflineDeviceCache(ctx, device, *existing); err != nil {
		return false, nil, err
	}

	return false, existing, nil
}

func markDeviceOnline(ctx context.Context, device string) (*offlineDeviceCache, bool, error) {
	existing, err := getOfflineDeviceCache(ctx, device)
	if err != nil {
		return nil, false, err
	}
	if existing == nil {
		return nil, false, nil
	}

	if err := redisClient.Del(ctx, device).Err(); err != nil {
		return nil, false, fmt.Errorf("failed to delete Redis cache for `%s`: %w", device, err)
	}

	return existing, true, nil
}
