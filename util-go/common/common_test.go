package common

import (
	"math"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

func TestGetTimeNowReturnsRequestedTimezone(t *testing.T) {
	now := GetTimeNow("Europe/Paris")

	loc, err := time.LoadLocation("Europe/Paris")
	if err != nil {
		t.Fatalf("failed to load timezone in test: %v", err)
	}

	if now.Location().String() != loc.String() {
		t.Fatalf("expected location %q, got %q", loc.String(), now.Location().String())
	}
}

func TestGetTimeNowIsTheCurrentMoment(t *testing.T) {
	before := time.Now()
	now := GetTimeNow("Europe/Paris")
	after := time.Now()

	if now.Before(before) || now.After(after) {
		t.Fatalf("expected a time between %v and %v, got %v", before, after, now)
	}
}

func TestGetTimeNowWallTimeIsInTheRequestedTimezone(t *testing.T) {
	now := GetTimeNow("Europe/Paris")

	// Paris is UTC+1 in winter and UTC+2 in summer.
	_, offset := now.Zone()
	if offset != 3600 && offset != 7200 {
		t.Fatalf("expected an offset of 1 or 2 hours, got %d seconds", offset)
	}
}

func TestGetTimeNowWithoutTimezoneIsUTC(t *testing.T) {
	// Documents the current behavior: time.LoadLocation("") is UTC, not an error.
	if got := GetTimeNow("").Location(); got != time.UTC {
		t.Fatalf("expected UTC, got %v", got)
	}
}

func TestGetTimeNowInvalidTimezoneFatal(t *testing.T) {
	if testutil.InChild(t) {
		GetTimeNow("Invalid/Timezone")
		return
	}

	result := testutil.RunInChild(t)

	if result.ExitCode != 1 {
		t.Fatalf("expected exit code 1, got %d:\n%s", result.ExitCode, result.Output())
	}
	if !strings.Contains(result.Output(), "Error loading timezone: unknown time zone Invalid/Timezone") {
		t.Fatalf("expected the timezone error to be logged, got:\n%s", result.Output())
	}
}

func TestGetTimeNowInvalidTimezoneIsReportedToSentry(t *testing.T) {
	if testutil.InChild(t) {
		logging.InitSentry(os.Getenv(testutil.SentryDSNEnv), "Collector status notifier")
		GetTimeNow("Invalid/Timezone")
		return
	}

	sentry := testutil.NewFakeSentry(t)
	testutil.RunInChild(t, testutil.SentryDSNEnv+"="+sentry.DSN())

	testutil.ExpectFailure(t, "GetTimeNow exits with log.Fatalf, which skips Sentry.", func(t testutil.TB) {
		if events := sentry.WaitForEvents(1, time.Second); len(events) != 1 || events[0].Level != "fatal" {
			t.Fatalf("expected one fatal event in Sentry, got %+v", events)
		}
	})
}

func TestGetPercentage(t *testing.T) {
	tests := []struct {
		name     string
		part     float64
		whole    float64
		expected float64
	}{
		{"normal case", 50, 200, 25},
		{"half", 1, 2, 50},
		{"zero part", 0, 100, 0},
		{"decimal", 2.5, 10, 25},
		{"zero whole", 1, 0, 0},
		{"zero of zero", 0, 0, 0},
		{"over the limit", 12, 10, 120},
		{"negative part", -5, 10, -50},
		{"small fraction", 1, 3, 100.0 / 3},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := GetPercentage(tt.part, tt.whole)
			if math.Abs(result-tt.expected) > 1e-9 {
				t.Errorf("expected %f, got %f", tt.expected, result)
			}
		})
	}
}
