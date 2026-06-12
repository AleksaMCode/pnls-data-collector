package main

import "testing"

func TestNormalizePath(t *testing.T) {
	testCases := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "empty path stays empty",
			input:    "",
			expected: "",
		},
		{
			name:     "whitespace path stays empty",
			input:    "   ",
			expected: "",
		},
		{
			name:     "already normalized path remains unchanged",
			input:    "/check",
			expected: "/check",
		},
		{
			name:     "missing leading slash gets prefixed",
			input:    "check",
			expected: "/check",
		},
		{
			name:     "trimmed path without leading slash gets prefixed",
			input:    "  trigger  ",
			expected: "/trigger",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			actual := normalizePath(testCase.input)
			if actual != testCase.expected {
				t.Fatalf("normalizePath(%q) = %q, expected %q", testCase.input, actual, testCase.expected)
			}
		})
	}
}
