package main

import (
	"strings"
	"testing"
)

func TestSelectOperationsQuery(t *testing.T) {
	tests := []struct {
		name       string
		hasBucket  bool
		expected   string
		contains   string
		notContain string
	}{
		{
			name:       "account only query",
			hasBucket:  false,
			expected:   r2OperationsAccountQuery,
			contains:   "$accountTag",
			notContain: "$bucketName",
		},
		{
			name:       "account with bucket query",
			hasBucket:  true,
			expected:   r2OperationsAccountBucketQuery,
			contains:   "$bucketName",
			notContain: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := selectOperationsQuery(tt.hasBucket)
			if got == "" {
				t.Fatal("selected operations query should not be empty")
			}
			if got != tt.expected {
				t.Fatal("selected operations query did not match expected embedded query")
			}
			if tt.contains != "" && !strings.Contains(got, tt.contains) {
				t.Fatalf("selected operations query should contain %q", tt.contains)
			}
			if tt.notContain != "" && strings.Contains(got, tt.notContain) {
				t.Fatalf("selected operations query should not contain %q", tt.notContain)
			}
		})
	}
}

func TestSelectStorageQuery(t *testing.T) {
	tests := []struct {
		name       string
		hasBucket  bool
		expected   string
		contains   string
		notContain string
	}{
		{
			name:       "account only query",
			hasBucket:  false,
			expected:   r2StorageAccountQuery,
			contains:   "$accountTag",
			notContain: "$bucketName",
		},
		{
			name:       "account with bucket query",
			hasBucket:  true,
			expected:   r2StorageAccountBucketQuery,
			contains:   "$bucketName",
			notContain: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := selectStorageQuery(tt.hasBucket)
			if got == "" {
				t.Fatal("selected storage query should not be empty")
			}
			if got != tt.expected {
				t.Fatal("selected storage query did not match expected embedded query")
			}
			if tt.contains != "" && !strings.Contains(got, tt.contains) {
				t.Fatalf("selected storage query should contain %q", tt.contains)
			}
			if tt.notContain != "" && strings.Contains(got, tt.notContain) {
				t.Fatalf("selected storage query should not contain %q", tt.notContain)
			}
		})
	}
}
