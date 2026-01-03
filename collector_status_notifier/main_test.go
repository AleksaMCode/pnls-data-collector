package main

import (
	"testing"
)

func TestValidateFirebaseNode(t *testing.T) {
	tests := []struct {
		deviceKey string
		today     string
		expected  bool
	}{
		{
			deviceKey: "RPI-1-2023-01-01",
			today:     "2023-01-01",
			expected:  true,
		},
		{
			deviceKey: "RPI-2-2023-01-01",
			today:     "2023-01-01",
			expected:  true,
		},
		{
			deviceKey: "RPI-4-2023-01-01",
			today:     "2023-01-01",
			expected:  false,
		},
		{
			deviceKey: "RPI-1-2023-01-02",
			today:     "2023-01-01",
			expected:  false,
		},
		{
			deviceKey: "RPI-1-2023-01-01",
			today:     "2023-01-02",
			expected:  false,
		},
		{
			deviceKey: "",
			today:     "2023-01-01",
			expected:  false,
		},
		{
			deviceKey: "RPI-1-2023-01-01",
			today:     "",
			expected:  false,
		},
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
