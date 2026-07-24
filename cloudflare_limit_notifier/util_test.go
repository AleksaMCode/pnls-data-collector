package main

import (
	"strings"
	"testing"
)

func TestGetPositiveIntEnv(t *testing.T) {
	tests := []struct {
		name        string
		envValue    *string
		fallback    int
		expected    int
		expectedErr string
	}{
		{
			name:     "returns fallback when env is missing",
			envValue: nil,
			fallback: 7,
			expected: 7,
		},
		{
			name:     "returns parsed value when env is valid",
			envValue: strPtr("12"),
			fallback: 7,
			expected: 12,
		},
		{
			name:        "returns error for non integer",
			envValue:    strPtr("abc"),
			fallback:    7,
			expectedErr: "must be an integer",
		},
		{
			name:        "returns error for zero",
			envValue:    strPtr("0"),
			fallback:    7,
			expectedErr: "must be > 0",
		},
		{
			name:        "returns error for negative",
			envValue:    strPtr("-3"),
			fallback:    7,
			expectedErr: "must be > 0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			const envKey = "TEST_POSITIVE_INT_ENV"
			if tt.envValue == nil {
				t.Setenv(envKey, "")
			} else {
				t.Setenv(envKey, *tt.envValue)
			}

			got, err := getPositiveIntEnv(envKey, tt.fallback)
			if tt.expectedErr != "" {
				if err == nil {
					t.Fatalf("expected error containing %q, got nil", tt.expectedErr)
				}
				if !strings.Contains(err.Error(), tt.expectedErr) {
					t.Fatalf("expected error containing %q, got %q", tt.expectedErr, err.Error())
				}
				return
			}

			if err != nil {
				t.Fatalf("expected nil error, got %v", err)
			}
			if got != tt.expected {
				t.Fatalf("getPositiveIntEnv() = %d, expected %d", got, tt.expected)
			}
		})
	}
}

func TestGetPositiveUintEnv(t *testing.T) {
	tests := []struct {
		name        string
		envValue    *string
		fallback    int
		expected    uint
		expectedErr string
	}{
		{
			name:     "returns fallback when env is missing",
			envValue: nil,
			fallback: 4,
			expected: 4,
		},
		{
			name:     "returns parsed value when env is valid",
			envValue: strPtr("9"),
			fallback: 4,
			expected: 9,
		},
		{
			name:        "returns error for non integer",
			envValue:    strPtr("abc"),
			fallback:    4,
			expectedErr: "must be an integer",
		},
		{
			name:        "returns error for zero",
			envValue:    strPtr("0"),
			fallback:    4,
			expectedErr: "must be > 0",
		},
		{
			name:        "returns error for negative",
			envValue:    strPtr("-1"),
			fallback:    4,
			expectedErr: "must be > 0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			const envKey = "TEST_POSITIVE_UINT_ENV"
			if tt.envValue == nil {
				t.Setenv(envKey, "")
			} else {
				t.Setenv(envKey, *tt.envValue)
			}

			got, err := getPositiveUintEnv(envKey, tt.fallback)
			if tt.expectedErr != "" {
				if err == nil {
					t.Fatalf("expected error containing %q, got nil", tt.expectedErr)
				}
				if !strings.Contains(err.Error(), tt.expectedErr) {
					t.Fatalf("expected error containing %q, got %q", tt.expectedErr, err.Error())
				}
				return
			}

			if err != nil {
				t.Fatalf("expected nil error, got %v", err)
			}
			if got != tt.expected {
				t.Fatalf("getPositiveUintEnv() = %d, expected %d", got, tt.expected)
			}
		})
	}
}

func strPtr(value string) *string {
	return &value
}
