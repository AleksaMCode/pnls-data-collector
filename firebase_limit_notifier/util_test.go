package main

import (
	"encoding/json"
	"testing"
)

func TestBytesToMB(t *testing.T) {
	tests := []struct {
		name     string
		bytes    int
		expected float64
	}{
		{
			name:     "zero bytes",
			bytes:    0,
			expected: 0,
		},
		{
			name:     "one MB",
			bytes:    1024 * 1024,
			expected: 1,
		},
		{
			name:     "half MB",
			bytes:    512 * 1024,
			expected: 0.5,
		},
		{
			name:     "two MB",
			bytes:    2 * 1024 * 1024,
			expected: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := bytesToMB(tt.bytes)
			if result != tt.expected {
				t.Errorf("bytesToMB(%d) = %f, want %f", tt.bytes, result, tt.expected)
			}
		})
	}
}

func TestGetNodeSize(t *testing.T) {
	tests := []struct {
		name string
		node any
	}{
		{
			name: "simple map",
			node: map[string]any{
				"id":   123,
				"name": "node1",
			},
		},
		{
			name: "nested structure",
			node: map[string]any{
				"id": 1,
				"metadata": map[string]any{
					"region": "us-east-1",
					"active": true,
				},
			},
		},
		{
			name: "slice of objects",
			node: []map[string]any{
				{"a": 1},
				{"b": 2},
			},
		},
		{
			name: "struct input",
			node: struct {
				ID   int    `json:"id"`
				Name string `json:"name"`
			}{
				ID:   10,
				Name: "test",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Marshal manually to calculate expected size
			b, err := json.Marshal(tt.node)
			if err != nil {
				t.Fatalf("json.Marshal failed: %v", err)
			}

			expected := float64(len(b)) / (1024 * 1024)
			result, _ := getNodeSize(tt.node)

			if result != expected {
				t.Errorf("getNodeSize() = %f, want %f", result, expected)
			}
		})
	}
}

func TestGetNodeSize_InvalidInput(t *testing.T) {
	_, err := getNodeSize(func() {})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func almostEqual(a, b, tolerance float64) bool {
	if a > b {
		return a-b < tolerance
	}
	return b-a < tolerance
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
		{"decimal-2", 1, 3, 33.3333333333},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := getPercentage(tt.part, tt.whole)
			if !almostEqual(result, tt.expected, 0.000001) {
				t.Errorf("expected %f, got %f", tt.expected, result)
			}
		})
	}
}
