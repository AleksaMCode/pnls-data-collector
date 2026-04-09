package main

import "testing"

func TestClassifyActionType(t *testing.T) {
	tests := []struct {
		actionType string
		expected   string
	}{
		{actionType: "PutObject", expected: "A"},
		{actionType: "ListObjects", expected: "A"},
		{actionType: "GetObject", expected: "B"},
		{actionType: "HeadObject", expected: "B"},
		{actionType: "UnknownAction", expected: "A"},
		{actionType: "", expected: "unknown"},
	}

	for _, tt := range tests {
		got := classifyActionType(tt.actionType)
		if got != tt.expected {
			t.Fatalf("classifyActionType(%q) = %q, expected %q", tt.actionType, got, tt.expected)
		}
	}
}
