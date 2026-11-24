package main

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestCheckFirebaseUsageHandlerRejectsNonPost(t *testing.T) {
	methods := []string{http.MethodGet, http.MethodPut, http.MethodDelete}

	for _, method := range methods {
		t.Run(method, func(t *testing.T) {
			checkRuns := 0
			handler := newCheckFirebaseUsageHandler(func() error {
				checkRuns++
				return nil
			})

			recorder := httptest.NewRecorder()
			handler(recorder, httptest.NewRequest(method, CHECK_PATH, nil))

			if recorder.Code != http.StatusMethodNotAllowed {
				t.Errorf("status = %d, want %d", recorder.Code, http.StatusMethodNotAllowed)
			}
			if checkRuns != 0 {
				t.Errorf("check ran %d times, want 0", checkRuns)
			}
		})
	}
}

func TestCheckFirebaseUsageHandlerRunsCheckOnPost(t *testing.T) {
	checkRuns := 0
	handler := newCheckFirebaseUsageHandler(func() error {
		checkRuns++
		return nil
	})

	recorder := httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodPost, CHECK_PATH, nil))

	if recorder.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusOK)
	}
	if checkRuns != 1 {
		t.Errorf("check ran %d times, want 1", checkRuns)
	}
	if recorder.Body.Len() == 0 {
		t.Error("expected a response body, got none")
	}
}

func TestCheckFirebaseUsageHandlerReportsFailedCheck(t *testing.T) {
	handler := newCheckFirebaseUsageHandler(func() error {
		return errors.New("failed to send message to Mattermost: connection refused")
	})

	recorder := httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodPost, CHECK_PATH, nil))

	if recorder.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want %d", recorder.Code, http.StatusBadGateway)
	}

	// The handler must keep serving requests after a failed check
	recorder = httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodPost, CHECK_PATH, nil))
	if recorder.Code != http.StatusBadGateway {
		t.Errorf("status after a second failed check = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
}
