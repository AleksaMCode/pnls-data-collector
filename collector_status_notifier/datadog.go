package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const datadogQueryWindow = 5 * time.Minute

type datadogQueryResponse struct {
	Status string   `json:"status"`
	Errors []string `json:"errors"`
	Series []struct {
		Pointlist [][]*float64 `json:"pointlist"`
	} `json:"series"`
}

func validateDatadogDeviceData(ctx context.Context) error {
	if DATADOG_API_KEY == "" || DATADOG_APP_KEY == "" || DATADOG_HEARTBEAT_METRIC == "" || DATADOG_HOST == "" {
		return fmt.Errorf("missing Datadog configuration")
	}

	client := &http.Client{
		Timeout: 8 * time.Second,
	}

	for _, device := range Devices {
		lastSeen, err := getDatadogLastSeen(ctx, client, device)
		if err != nil {
			return err
		}

		if lastSeen.IsZero() {
			message := fmt.Sprintf(
				"Device `%s` has no `%s` datapoints in Datadog within the last %s",
				device,
				DATADOG_HEARTBEAT_METRIC,
				datadogQueryWindow.String(),
			)
			sendMattermostMsg(message)
			continue
		}

		if time.Since(lastSeen) > DATADOG_TIMEOUT {
			message := fmt.Sprintf(
				"Device `%s` heartbeat is stale in Datadog. Last update: %s (threshold: %s)",
				device,
				lastSeen.Format(time.RFC3339),
				DATADOG_TIMEOUT.String(),
			)
			sendMattermostMsg(message)
			continue
		} else {
			log.Printf("Device `%s` was recently updated at %s", device, lastSeen.Format(time.RFC3339))
		}
	}

	return nil
}

func getDatadogLastSeen(ctx context.Context, client *http.Client, device string) (time.Time, error) {
	now := time.Now().Unix()
	from := now - int64(datadogQueryWindow.Seconds())
	query := fmt.Sprintf("avg:%s{host:%s}", DATADOG_HEARTBEAT_METRIC, device)

	requestURL := fmt.Sprintf(
		"%s/api/v1/query?from=%s&to=%s&query=%s",
		DATADOG_HOST,
		strconv.FormatInt(from, 10),
		strconv.FormatInt(now, 10),
		url.QueryEscape(query),
	)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return time.Time{}, fmt.Errorf("creating Datadog request for device `%s`: %w", device, err)
	}

	req.Header.Set("DD-API-KEY", DATADOG_API_KEY)
	req.Header.Set("DD-APPLICATION-KEY", DATADOG_APP_KEY)

	resp, err := client.Do(req)
	if err != nil {
		return time.Time{}, fmt.Errorf("requesting Datadog status for device `%s`: %w", device, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return time.Time{}, fmt.Errorf(
			"Datadog returned HTTP %d for device `%s`: %s",
			resp.StatusCode,
			device,
			strings.TrimSpace(string(body)),
		)
	}

	var parsed datadogQueryResponse
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return time.Time{}, fmt.Errorf("decoding Datadog response for device `%s`: %w", device, err)
	}

	if len(parsed.Errors) > 0 {
		return time.Time{}, fmt.Errorf(
			"Datadog query error for device `%s`: %s",
			device,
			strings.Join(parsed.Errors, "; "),
		)
	}

	lastSeen := extractLastSeen(parsed)
	return lastSeen, nil
}

func extractLastSeen(response datadogQueryResponse) time.Time {
	var lastSeen time.Time

	for _, series := range response.Series {
		for _, point := range series.Pointlist {
			if len(point) < 2 || point[0] == nil || point[1] == nil {
				continue
			}

			millis := int64(*point[0])
			current := time.UnixMilli(millis)
			if current.After(lastSeen) {
				lastSeen = current
			}
		}
	}

	return lastSeen
}
