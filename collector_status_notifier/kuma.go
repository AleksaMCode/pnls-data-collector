package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
)

// validateKumaConfig checks that a usable push URL is set when the Uptime Kuma push is enabled.
func validateKumaConfig(enabled bool, pushURL string) error {
	if !enabled {
		return nil
	}
	if pushURL == "" {
		return fmt.Errorf("KUMA_PUSH_URL must be set when KUMA_PUSH_ENABLED is true")
	}

	parsedURL, err := url.Parse(pushURL)
	if err != nil || parsedURL.Host == "" || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") {
		return fmt.Errorf("KUMA_PUSH_URL must be a valid http(s) URL")
	}
	return nil
}

// sendKumaPush reports a heartbeat to Uptime Kuma, which marks the service as down when the heartbeats stop.
// A failed push is only logged, so that an unreachable Uptime Kuma never stops the status checks.
func sendKumaPush(ctx context.Context) {
	if !KUMA_PUSH_ENABLED {
		return
	}

	if err := pushKumaHeartbeat(ctx, KUMA_PUSH_URL); err != nil {
		log.Printf("Uptime Kuma push failed: %v", err)
	}
}

func pushKumaHeartbeat(ctx context.Context, pushURL string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, pushURL, nil)
	if err != nil {
		return redactPushURL(err)
	}

	client := &http.Client{Timeout: KUMA_PUSH_TIMEOUT}
	resp, err := client.Do(req)
	if err != nil {
		return redactPushURL(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("unexpected status code %d", resp.StatusCode)
	}
	return nil
}

// redactPushURL drops the request URL from an HTTP client error and keeps only the failure cause.
// The push URL holds the monitor's token in its path, so it must not end up in the logs.
func redactPushURL(err error) error {
	var urlErr *url.Error
	if errors.As(err, &urlErr) {
		return fmt.Errorf("%s request failed: %w", urlErr.Op, urlErr.Err)
	}
	return err
}
