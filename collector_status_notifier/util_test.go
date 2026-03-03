package main

import (
	"testing"

	common "github.com/AleksaMCode/pnls-data-collector/util-go/common"
)

func TestIsWorkingHoursMatchesTimezoneHourRule(t *testing.T) {
	now := common.GetTimeNow(TIMEZONE)
	expected := now.Hour() >= 6 && now.Hour() < 18

	if got := isWorkingHours(); got != expected {
		t.Fatalf("isWorkingHours() = %v, expected %v for hour %d", got, expected, now.Hour())
	}
}
