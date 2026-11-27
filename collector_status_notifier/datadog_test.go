package main

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func float(value float64) *float64 {
	return &value
}

func TestGetDatadogLastSeenQueriesTheHeartbeat(t *testing.T) {
	fake := useFakeDatadog(t)
	beat := time.Now().Add(-10 * time.Second).Truncate(time.Millisecond)
	fake.heartbeat(DEVICE_RPI_2, beat.Add(-time.Minute), beat)

	started := time.Now().Unix()
	lastSeen, err := getDatadogLastSeen(context.Background(), http.DefaultClient, DEVICE_RPI_2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if !lastSeen.Equal(beat) {
		t.Errorf("lastSeen = %s, want %s", lastSeen, beat)
	}
	queries := fake.received()
	if len(queries) != 1 {
		t.Fatalf("expected one query, got %d", len(queries))
	}
	query := queries[0]
	if query.apiKey != "api-key" || query.appKey != "app-key" {
		t.Errorf("sent the keys %q and %q", query.apiKey, query.appKey)
	}
	if query.query != "avg:pnls.heartbeat{host:RPI-2}" {
		t.Errorf("query = %q", query.query)
	}
	if query.to < started || query.to-query.from != int64(COLLECTOR_TIMEOUT.Seconds()) {
		t.Errorf("queried %d to %d, want the last %s", query.from, query.to, COLLECTOR_TIMEOUT)
	}
}

func TestGetDatadogLastSeenWithoutPoints(t *testing.T) {
	useFakeDatadog(t)

	lastSeen, err := getDatadogLastSeen(context.Background(), http.DefaultClient, DEVICE_RPI_1)

	if err != nil || !lastSeen.IsZero() {
		t.Fatalf("expected no heartbeat, got %s, %v", lastSeen, err)
	}
}

func TestGetDatadogLastSeenErrors(t *testing.T) {
	testCases := []struct {
		name    string
		status  int
		body    string
		wantErr string
	}{
		{
			name:    "error status",
			status:  http.StatusForbidden,
			body:    ` {"errors":["Forbidden"]} `,
			wantErr: "unexpected HTTP 403 from Datadog for device `RPI-1`: {\"errors\":[\"Forbidden\"]}",
		},
		{
			name:    "query errors",
			status:  http.StatusOK,
			body:    `{"status":"error","errors":["bad metric","bad tag"]}`,
			wantErr: "querying Datadog for device `RPI-1`: bad metric; bad tag",
		},
		{
			name:    "invalid JSON",
			status:  http.StatusOK,
			body:    `<html>maintenance</html>`,
			wantErr: "decoding Datadog response for device `RPI-1`",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			fake := useFakeDatadog(t)
			fake.fail(DEVICE_RPI_1, testCase.status, testCase.body)

			_, err := getDatadogLastSeen(context.Background(), http.DefaultClient, DEVICE_RPI_1)

			if err == nil || !strings.Contains(err.Error(), testCase.wantErr) {
				t.Fatalf("expected %q, got %v", testCase.wantErr, err)
			}
		})
	}
}

func TestGetDatadogLastSeenCutsALongErrorBody(t *testing.T) {
	fake := useFakeDatadog(t)
	fake.fail(DEVICE_RPI_1, http.StatusBadGateway, strings.Repeat("z", 5000))

	_, err := getDatadogLastSeen(context.Background(), http.DefaultClient, DEVICE_RPI_1)

	if err == nil || strings.Count(err.Error(), "z") != 2048 {
		t.Fatalf("expected the body cut at 2048 bytes, got %d bytes", strings.Count(err.Error(), "z"))
	}
}

func TestGetDatadogLastSeenWhenDatadogCantBeReached(t *testing.T) {
	useFakeDatadog(t)
	DATADOG_HOST = testutil.RefusedURL()

	_, err := getDatadogLastSeen(context.Background(), http.DefaultClient, DEVICE_RPI_1)

	if err == nil || !strings.Contains(err.Error(), "requesting Datadog status for device `RPI-1`") {
		t.Fatalf("expected the request error, got %v", err)
	}
}

func TestGetDatadogLastSeenWithAnInvalidHost(t *testing.T) {
	useFakeDatadog(t)
	DATADOG_HOST = "http://[::1"

	_, err := getDatadogLastSeen(context.Background(), http.DefaultClient, DEVICE_RPI_1)

	if err == nil || !strings.Contains(err.Error(), "creating Datadog request for device `RPI-1`") {
		t.Fatalf("expected the request error, got %v", err)
	}
}

func TestGetDatadogLastSeenStopsWithTheContext(t *testing.T) {
	useFakeDatadog(t)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	_, err := getDatadogLastSeen(ctx, http.DefaultClient, DEVICE_RPI_1)

	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected the cancellation, got %v", err)
	}
}

func TestExtractLastSeen(t *testing.T) {
	response := datadogQueryResponse{}
	response.Series = append(response.Series,
		struct {
			Pointlist [][]*float64 `json:"pointlist"`
		}{Pointlist: [][]*float64{
			{float(1_000), float(1)},
			{float(5_000), nil}, // a bucket without a value
			{nil, float(1)},
			{float(9_000)},
		}},
		struct {
			Pointlist [][]*float64 `json:"pointlist"`
		}{Pointlist: [][]*float64{{float(3_000), float(1)}}},
	)

	if got := extractLastSeen(response); !got.Equal(time.UnixMilli(3_000)) {
		t.Fatalf("extractLastSeen() = %s, want the latest point with a value", got)
	}
	if got := extractLastSeen(datadogQueryResponse{}); !got.IsZero() {
		t.Fatalf("extractLastSeen() without series = %s, want zero", got)
	}
}

func TestValidateDatadogDeviceDataRequiresTheConfiguration(t *testing.T) {
	for _, name := range []string{"DATADOG_API_KEY", "DATADOG_APP_KEY", "DATADOG_HEARTBEAT_METRIC", "DATADOG_HOST"} {
		t.Run(name, func(t *testing.T) {
			fake := useFakeDatadog(t)
			*configVariables()[name] = ""

			if err := validateDatadogDeviceData(context.Background()); err == nil ||
				err.Error() != "missing Datadog configuration" {
				t.Fatalf("expected the missing configuration, got %v", err)
			}
			if len(fake.received()) != 0 {
				t.Error("expected no query")
			}
		})
	}
}

func TestValidateDatadogDeviceDataReportsEachDevice(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeDatadog(t)
	useMiniredis(t)
	webhook := useWebhook(t)
	now := time.Now()
	fake.heartbeat(DEVICE_RPI_1, now.Add(-5*time.Second))
	fake.heartbeat(DEVICE_RPI_2, now.Add(-2*time.Minute))
	// RPI-3 has no points.

	if err := validateDatadogDeviceData(context.Background()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	messages := texts(webhook)
	if len(messages) != 2 {
		t.Fatalf("expected two alerts, got %q", messages)
	}
	if !strings.HasPrefix(messages[0], "Device `RPI-2` heartbeat is stale in Datadog. Last update: ") ||
		!strings.HasSuffix(messages[0], "(threshold: 30s)") {
		t.Errorf("unexpected stale alert %q", messages[0])
	}
	if messages[1] != "Device `RPI-3` has no `pnls.heartbeat` datapoints in Datadog within the last 5m0s" {
		t.Errorf("unexpected missing alert %q", messages[1])
	}
	if cachedOffline(t, DEVICE_RPI_1) != nil || cachedOffline(t, DEVICE_RPI_2) == nil ||
		cachedOffline(t, DEVICE_RPI_3) == nil {
		t.Error("expected RPI-2 and RPI-3 cached as offline, and RPI-1 not")
	}
}

func TestValidateDatadogDeviceDataStopsAtTheFirstError(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeDatadog(t)
	useMiniredis(t)
	useWebhook(t)
	fake.heartbeat(DEVICE_RPI_1, time.Now())
	fake.fail(DEVICE_RPI_2, http.StatusInternalServerError, "down")

	err := validateDatadogDeviceData(context.Background())

	if err == nil || !strings.Contains(err.Error(), "unexpected HTTP 500 from Datadog for device `RPI-2`") {
		t.Fatalf("expected RPI-2's error, got %v", err)
	}
	if queries := fake.received(); len(queries) != 2 {
		t.Errorf("expected RPI-3 not to be queried, got %d queries", len(queries))
	}
}
