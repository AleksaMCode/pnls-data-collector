package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"

	retry "github.com/avast/retry-go/v4"
)

type usageMetrics struct {
	ClassARequests float64
	ClassBRequests float64
	StorageBytes   float64
}

type gqlRequest struct {
	Query     string         `json:"query"`
	Variables map[string]any `json:"variables"`
}

type gqlError struct {
	Message string `json:"message"`
}

type gqlResponse struct {
	Data   json.RawMessage `json:"data"`
	Errors []gqlError      `json:"errors"`
}

type operationsData struct {
	Viewer struct {
		Accounts []struct {
			R2OperationsAdaptiveGroups []struct {
				Dimensions struct {
					ActionType string `json:"actionType"`
				} `json:"dimensions"`
				Sum struct {
					Requests float64 `json:"requests"`
				} `json:"sum"`
			} `json:"r2OperationsAdaptiveGroups"`
		} `json:"accounts"`
	} `json:"viewer"`
}

type storageData struct {
	Viewer struct {
		Accounts []struct {
			R2StorageAdaptiveGroups []struct {
				Dimensions struct {
					BucketName string `json:"bucketName"`
					Datetime   string `json:"datetime"`
				} `json:"dimensions"`
				Max struct {
					PayloadSize  float64 `json:"payloadSize"`
					MetadataSize float64 `json:"metadataSize"`
				} `json:"max"`
			} `json:"r2StorageAdaptiveGroups"`
		} `json:"accounts"`
	} `json:"viewer"`
}

type cloudflareClient struct {
	httpClient *http.Client
	endpoint   string
	token      string
	accountTag string
}

type retryableHTTPError struct {
	statusCode int
	body       string
	retryAfter time.Duration
}

func (e *retryableHTTPError) Error() string {
	return fmt.Sprintf("cloudflare graphql returned status %d: %s", e.statusCode, e.body)
}

func newCloudflareClient() *cloudflareClient {
	return &cloudflareClient{
		httpClient: &http.Client{Timeout: 30 * time.Second},
		endpoint:   CLOUDFLARE_GRAPHQL_ENDPOINT,
		token:      CLOUDFLARE_API_TOKEN,
		accountTag: CLOUDFLARE_ACCOUNT_ID,
	}
}

func (c *cloudflareClient) getCurrentMonthUsage(now time.Time) (usageMetrics, error) {
	start := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, now.Location())

	classA, classB, err := c.fetchOperations(start, now)
	if err != nil {
		return usageMetrics{}, err
	}

	storageBytes, err := c.fetchStorage(start, now)
	if err != nil {
		return usageMetrics{}, err
	}

	return usageMetrics{
		ClassARequests: classA,
		ClassBRequests: classB,
		StorageBytes:   storageBytes,
	}, nil
}

func (c *cloudflareClient) fetchOperations(start time.Time, end time.Time) (float64, float64, error) {
	query := selectOperationsQuery(CLOUDFLARE_R2_BUCKET_FILTER != "")

	variables := map[string]any{
		"accountTag":    c.accountTag,
		"datetimeStart": start.UTC().Format(time.RFC3339),
		"datetimeEnd":   end.UTC().Format(time.RFC3339),
		"limit":         GRAPHQL_LIMIT,
	}

	if CLOUDFLARE_R2_BUCKET_FILTER != "" {
		variables["bucketName"] = CLOUDFLARE_R2_BUCKET_FILTER
	}

	var result operationsData
	if err := c.query(query, variables, &result); err != nil {
		return 0, 0, err
	}

	if len(result.Viewer.Accounts) == 0 {
		return 0, 0, fmt.Errorf("no Cloudflare account data returned from operations dataset")
	}

	classA := 0.0
	classB := 0.0
	for _, account := range result.Viewer.Accounts {
		for _, row := range account.R2OperationsAdaptiveGroups {
			class := classifyActionType(row.Dimensions.ActionType)
			switch class {
			case "A":
				classA += row.Sum.Requests
			case "B":
				classB += row.Sum.Requests
			}
		}
	}

	return classA, classB, nil
}

func (c *cloudflareClient) fetchStorage(start time.Time, end time.Time) (float64, error) {
	query := selectStorageQuery(CLOUDFLARE_R2_BUCKET_FILTER != "")

	variables := map[string]any{
		"accountTag":    c.accountTag,
		"datetimeStart": start.UTC().Format(time.RFC3339),
		"datetimeEnd":   end.UTC().Format(time.RFC3339),
		"limit":         GRAPHQL_LIMIT,
	}
	if CLOUDFLARE_R2_BUCKET_FILTER != "" {
		variables["bucketName"] = CLOUDFLARE_R2_BUCKET_FILTER
	}

	var result storageData
	if err := c.query(query, variables, &result); err != nil {
		return 0, err
	}

	if len(result.Viewer.Accounts) == 0 {
		return 0, fmt.Errorf("no Cloudflare account data returned from storage dataset")
	}

	// Storage dataset is time-series based. To match Cloudflare console "current usage",
	// use the latest available point per bucket (not the month maximum).
	type bucketSnapshot struct {
		observedAt time.Time
		sizeBytes  float64
	}
	bucketToLatest := map[string]bucketSnapshot{}
	for _, account := range result.Viewer.Accounts {
		for _, row := range account.R2StorageAdaptiveGroups {
			bucket := row.Dimensions.BucketName
			observedAt, err := time.Parse(time.RFC3339, row.Dimensions.Datetime)
			if err != nil {
				// Skip malformed points instead of failing whole report.
				continue
			}

			current, exists := bucketToLatest[bucket]
			if !exists || observedAt.After(current.observedAt) {
				bucketToLatest[bucket] = bucketSnapshot{
					observedAt: observedAt,
					sizeBytes:  row.Max.PayloadSize + row.Max.MetadataSize,
				}
			}
		}
	}

	total := 0.0
	for _, snapshot := range bucketToLatest {
		total += snapshot.sizeBytes
	}
	return total, nil
}

func (c *cloudflareClient) query(query string, variables map[string]any, out any) error {
	payload := gqlRequest{
		Query:     query,
		Variables: variables,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	err = retry.Do(
		func() error {
			req, reqErr := http.NewRequest(http.MethodPost, c.endpoint, bytes.NewReader(body))
			if reqErr != nil {
				return retry.Unrecoverable(reqErr)
			}
			req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.token))
			req.Header.Set("Content-Type", "application/json")

			resp, doErr := c.httpClient.Do(req)
			if doErr != nil {
				return doErr
			}
			defer resp.Body.Close()

			respBody, readErr := io.ReadAll(resp.Body)
			if readErr != nil {
				return readErr
			}
			if resp.StatusCode >= 400 {
				httpErr := &retryableHTTPError{
					statusCode: resp.StatusCode,
					body:       string(respBody),
				}
				if resp.StatusCode == http.StatusTooManyRequests {
					if retryAfter, ok := parseRetryAfterHeader(resp.Header.Get("Retry-After"), time.Now()); ok {
						httpErr.retryAfter = retryAfter
					}
				}
				if isRetryableHTTPStatus(resp.StatusCode) {
					return httpErr
				}
				return retry.Unrecoverable(httpErr)
			}

			var gqlResp gqlResponse
			if unmarshalErr := json.Unmarshal(respBody, &gqlResp); unmarshalErr != nil {
				return retry.Unrecoverable(unmarshalErr)
			}
			if len(gqlResp.Errors) > 0 {
				messages := make([]string, 0, len(gqlResp.Errors))
				for _, e := range gqlResp.Errors {
					messages = append(messages, e.Message)
				}
				return retry.Unrecoverable(fmt.Errorf("cloudflare graphql error(s): %s", strings.Join(messages, "; ")))
			}

			if unmarshalErr := json.Unmarshal(gqlResp.Data, out); unmarshalErr != nil {
				return retry.Unrecoverable(unmarshalErr)
			}
			return nil
		},
		retry.Attempts(GRAPHQL_RETRY_ATTEMPTS),
		retry.Delay(time.Duration(GRAPHQL_RETRY_DELAY)*time.Second),
		retry.MaxDelay(time.Duration(GRAPHQL_RETRY_MAX_DELAY)*time.Second),
		retry.LastErrorOnly(true),
		retry.DelayType(func(n uint, err error, _ *retry.Config) time.Duration {
			var httpErr *retryableHTTPError
			if errors.As(err, &httpErr) && httpErr.statusCode == http.StatusTooManyRequests && httpErr.retryAfter > 0 {
				return httpErr.retryAfter
			}
			return time.Duration(math.Pow(2, float64(n))) * time.Second
		}),
		retry.RetryIf(func(err error) bool {
			var httpErr *retryableHTTPError
			if errors.As(err, &httpErr) {
				return isRetryableHTTPStatus(httpErr.statusCode)
			}
			return true
		}),
		retry.OnRetry(func(n uint, err error) {
			log.Printf("Cloudflare GraphQL retry attempt %d due to error: %v", n+1, err)
		}),
	)
	return err
}

func isRetryableHTTPStatus(statusCode int) bool {
	return statusCode == http.StatusTooManyRequests || statusCode >= 500
}

func parseRetryAfterHeader(headerValue string, now time.Time) (time.Duration, bool) {
	if headerValue == "" {
		return 0, false
	}

	if seconds, err := strconv.Atoi(strings.TrimSpace(headerValue)); err == nil {
		if seconds <= 0 {
			return 0, false
		}
		return time.Duration(seconds) * time.Second, true
	}

	if retryAt, err := http.ParseTime(headerValue); err == nil {
		delay := retryAt.Sub(now)
		if delay > 0 {
			return delay, true
		}
	}
	return 0, false
}

func classifyActionType(actionType string) string {
	action := strings.ToLower(actionType)
	if action == "" {
		return "unknown"
	}

	// Class B is read-like traffic. Treat all other known operation names as Class A
	// to avoid undercounting due uncommon write/list action labels.
	classBKeywords := []string{
		"get", "head", "read", "download",
	}
	for _, keyword := range classBKeywords {
		if strings.Contains(action, keyword) {
			return "B"
		}
	}
	return "A"
}
