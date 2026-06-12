package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/joho/godotenv"
	"github.com/shirou/gopsutil/v4/disk"
)

type diskUsage struct {
	UsedBytes  float64
	FreeBytes  float64
	TotalBytes float64
}

func loadEnvVariables() {
	if err := godotenv.Load(); err != nil {
		logging.Fatal("Error loading .env file")
	}

	MATTERMOST_WEBHOOK_URL = strings.TrimSpace(os.Getenv("MATTERMOST_WEBHOOK_URL"))
	SENTRY_DSN = strings.TrimSpace(os.Getenv("SENTRY_DSN"))
	HTTP_PORT = strings.TrimSpace(os.Getenv("HTTP_PORT"))
	CHECK_ENDPOINT_PATH = strings.TrimSpace(os.Getenv("CHECK_ENDPOINT_PATH"))
	DISK_MOUNT_PATH = strings.TrimSpace(os.Getenv("DISK_MOUNT_PATH"))

	CHECK_ENDPOINT_PATH = normalizePath(CHECK_ENDPOINT_PATH)
}

func validateRequiredEnv() error {
	if MATTERMOST_WEBHOOK_URL == "" {
		return fmt.Errorf("missing MATTERMOST_WEBHOOK_URL")
	}
	if HTTP_PORT == "" {
		return fmt.Errorf("missing HTTP_PORT")
	}
	if CHECK_ENDPOINT_PATH == "" {
		return fmt.Errorf("missing CHECK_ENDPOINT_PATH")
	}
	if DISK_MOUNT_PATH == "" {
		return fmt.Errorf("missing DISK_MOUNT_PATH")
	}
	return nil
}

func normalizePath(path string) string {
	trimmedPath := strings.TrimSpace(path)
	if trimmedPath == "" {
		return ""
	}

	if strings.HasPrefix(trimmedPath, "/") {
		return trimmedPath
	}

	return "/" + trimmedPath
}

func getDiskUsage(mountPath string) (diskUsage, error) {
	usageStats, err := disk.Usage(mountPath)
	if err != nil {
		return diskUsage{}, fmt.Errorf("failed to read disk usage for %s: %w", mountPath, err)
	}

	totalBytes := float64(usageStats.Total)
	freeBytes := float64(usageStats.Free)
	usedBytes := totalBytes - freeBytes

	if totalBytes <= 0 {
		return diskUsage{}, fmt.Errorf("invalid total disk size for %s", mountPath)
	}

	return diskUsage{
		UsedBytes:  usedBytes,
		FreeBytes:  freeBytes,
		TotalBytes: totalBytes,
	}, nil
}

func formatUsageMessage(currentUsage diskUsage, mountPath string) string {
	usedGB := currentUsage.UsedBytes / BYTES_IN_GB
	freeGB := currentUsage.FreeBytes / BYTES_IN_GB
	totalGB := currentUsage.TotalBytes / BYTES_IN_GB

	return fmt.Sprintf(
		"Home server memory usage:\n* Mount path: `%s`\n* Used: %.2f GB / %.2f GB (%.2f%%)\n* Free: %.2f GB",
		mountPath,
		usedGB,
		totalGB,
		common.GetPercentage(currentUsage.UsedBytes, currentUsage.TotalBytes),
		freeGB,
	)
}
