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

func TestGetNodeSizeInvalidInput(t *testing.T) {
	_, err := getNodeSize(func() {})
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}
