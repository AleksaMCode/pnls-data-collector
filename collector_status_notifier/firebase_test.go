package main

import (
	"context"
	"net/http"
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func TestValidateFirebaseNode(t *testing.T) {
	tests := []struct {
		deviceKey string
		today     string
		expected  bool
	}{
		{deviceKey: "RPI-1-2023-01-01", today: "2023-01-01", expected: true},
		{deviceKey: "RPI-2-2023-01-01", today: "2023-01-01", expected: true},
		{deviceKey: "RPI-3-2023-01-01", today: "2023-01-01", expected: true},
		{deviceKey: "RPI-4-2023-01-01", today: "2023-01-01", expected: false},
		{deviceKey: "RPI-1-2023-01-02", today: "2023-01-01", expected: false},
		{deviceKey: "RPI-1-2023-01-01", today: "2023-01-02", expected: false},
		{deviceKey: "2023-01-01", today: "2023-01-01", expected: false},
		{deviceKey: "", today: "2023-01-01", expected: false},
		{deviceKey: "RPI-1-2023-01-01", today: "", expected: false},
	}

	for _, tt := range tests {
		t.Run(tt.deviceKey, func(t *testing.T) {
			actual := validateFirebaseNode(tt.deviceKey, tt.today)
			if actual != tt.expected {
				t.Errorf("validateFirebaseNode(%q, %q) = %v; expected %v", tt.deviceKey, tt.today, actual, tt.expected)
			}
		})
	}
}

func TestValidateFirebaseDeviceDataReportsEachDevice(t *testing.T) {
	logs := testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	now := parisNow(t)
	stale := now.Add(-20 * time.Minute)
	_, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, now): status(now.Add(-time.Minute)),
		statusNode(DEVICE_RPI_2, now): status(stale),
		// RPI-3 has no status, today or yesterday.
	})

	validateFirebaseDeviceData(context.Background(), client)

	want := []string{
		"Device `RPI-2` hasn't been updated in the last 11m0s! Last update: " + stale.Format(TIMESTAMP_FORMAT),
		"Device `RPI-3` has no status for today (" + now.Format("2006-01-02") + ")",
	}
	if got := texts(webhook); !slices.Equal(got, want) {
		t.Fatalf("alerts =\n%q\nwant\n%q", got, want)
	}
	if !strings.Contains(logs.String(), "Device `RPI-1` was recently updated at ") {
		t.Errorf("expected RPI-1 online in the log, got:\n%s", logs.String())
	}
	if cachedOffline(t, DEVICE_RPI_1) != nil {
		t.Error("expected RPI-1 not to be cached as offline")
	}
}

func TestValidateFirebaseDeviceDataReadsOnlyTheStatus(t *testing.T) {
	testutil.CaptureLog(t)
	useMiniredis(t)
	useWebhook(t)
	now := parisNow(t)
	fake, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, now): status(now),
		statusNode(DEVICE_RPI_2, now): status(now),
		statusNode(DEVICE_RPI_3, now): status(now),
	})

	validateFirebaseDeviceData(context.Background(), client)

	want := []string{statusNode(DEVICE_RPI_1, now), statusNode(DEVICE_RPI_2, now), statusNode(DEVICE_RPI_3, now)}
	if reads := fake.Reads(); !slices.Equal(reads, want) {
		t.Fatalf("read %q, want only today's statuses %q", reads, want)
	}
}

func TestValidateFirebaseDeviceDataFallsBackToYesterday(t *testing.T) {
	testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	now := parisNow(t)
	yesterday := now.AddDate(0, 0, -1)
	// Right after midnight, the last heartbeat is in yesterday's node.
	fake, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, yesterday): status(now.Add(-time.Minute)),
		statusNode(DEVICE_RPI_2, now):       status(now),
		statusNode(DEVICE_RPI_3, now):       status(now),
	})

	validateFirebaseDeviceData(context.Background(), client)

	if messages := texts(webhook); len(messages) != 0 {
		t.Fatalf("expected no alert, got %q", messages)
	}
	if reads := fake.Reads(); !slices.Contains(reads, statusNode(DEVICE_RPI_1, yesterday)) {
		t.Errorf("expected yesterday's status to be read, got %q", reads)
	}
}

func TestValidateFirebaseDeviceDataWithAnInvalidTimestamp(t *testing.T) {
	testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	now := parisNow(t)
	_, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, now): map[string]any{"status": "working", "timestamp": "27/11/2026 10:00"},
		statusNode(DEVICE_RPI_2, now): map[string]any{"status": "working"},
		statusNode(DEVICE_RPI_3, now): map[string]any{"status": "working", "timestamp": 1_795_728_892},
	})

	validateFirebaseDeviceData(context.Background(), client)

	want := []string{
		"Device `RPI-1` has invalid timestamp in Firebase status: \"27/11/2026 10:00\"",
		"Device `RPI-2` has invalid timestamp in Firebase status: \"\"",
		"Device `RPI-3` has invalid timestamp in Firebase status: \"\"",
	}
	if got := texts(webhook); !slices.Equal(got, want) {
		t.Fatalf("alerts =\n%q\nwant\n%q", got, want)
	}
}

func TestValidateFirebaseDeviceDataSkipsDevicesThatCantBeRead(t *testing.T) {
	logs := testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	now := parisNow(t)
	yesterday := now.AddDate(0, 0, -1)
	fake, client := newFakeFirebase(t, map[string]any{statusNode(DEVICE_RPI_3, now): status(now)})
	fake.FailReads(http.StatusForbidden, statusNode(DEVICE_RPI_1, now), statusNode(DEVICE_RPI_2, yesterday))

	validateFirebaseDeviceData(context.Background(), client)

	if messages := texts(webhook); len(messages) != 0 {
		t.Fatalf("expected no alert, got %q", messages)
	}
	for _, node := range []string{
		DEVICE_RPI_1 + "-" + now.Format("2006-01-02"),
		DEVICE_RPI_2 + "-" + yesterday.Format("2006-01-02"),
	} {
		if !strings.Contains(logs.String(), "Error fetching status for node "+node) {
			t.Errorf("expected the read error of %s in the log, got:\n%s", node, logs.String())
		}
	}
	if reads := fake.Reads(); slices.Contains(reads, statusNode(DEVICE_RPI_1, yesterday)) {
		t.Error("expected RPI-1's yesterday not to be read after today's read failed")
	}
}

func TestValidateFirebaseDeviceDataReadsTheTimestampInParisTime(t *testing.T) {
	testutil.CaptureLog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	now := parisNow(t)
	// 12 minutes ago in Paris is stale. Read as UTC, it would be an hour or two in the future, and look fresh.
	stale := now.Add(-12 * time.Minute)
	_, client := newFakeFirebase(t, map[string]any{
		statusNode(DEVICE_RPI_1, now): status(stale),
		statusNode(DEVICE_RPI_2, now): status(now),
		statusNode(DEVICE_RPI_3, now): status(now),
	})

	validateFirebaseDeviceData(context.Background(), client)

	if messages := texts(webhook); len(messages) != 1 || !strings.HasPrefix(messages[0], "Device `RPI-1` hasn't") {
		t.Fatalf("expected RPI-1 to be stale, got %q", messages)
	}
}
