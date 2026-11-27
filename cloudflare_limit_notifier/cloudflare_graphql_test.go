package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

// fakeAnswer is what the fake Cloudflare API answers to one request.
type fakeAnswer struct {
	status     int
	body       string
	retryAfter string
}

// graphqlCall is a request the fake Cloudflare API received.
type graphqlCall struct {
	method, authorization, contentType string
	request                            gqlRequest
}

// fakeCloudflare answers the GraphQL queries of the operations and storage datasets from its queues. The last answer
// of a queue repeats.
type fakeCloudflare struct {
	server     *httptest.Server
	mu         sync.Mutex
	operations []fakeAnswer
	storage    []fakeAnswer
	calls      []graphqlCall
	// timer records the delays of the retries, when useFakeCloudflare set the fake up.
	timer *recordingTimer
}

func newFakeCloudflare(t *testing.T) *fakeCloudflare {
	t.Helper()

	fake := &fakeCloudflare{
		operations: []fakeAnswer{ok(operationsBody())},
		storage:    []fakeAnswer{ok(storageBody())},
	}
	fake.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var request gqlRequest
		if err := json.Unmarshal(body, &request); err != nil {
			t.Errorf("expected a GraphQL request, got %q: %v", body, err)
		}

		fake.mu.Lock()
		fake.calls = append(fake.calls, graphqlCall{
			method:        r.Method,
			authorization: r.Header.Get("Authorization"),
			contentType:   r.Header.Get("Content-Type"),
			request:       request,
		})
		queue := &fake.storage
		if strings.Contains(request.Query, "r2OperationsAdaptiveGroups") {
			queue = &fake.operations
		}
		answer := (*queue)[0]
		if len(*queue) > 1 {
			*queue = (*queue)[1:]
		}
		fake.mu.Unlock()

		if answer.retryAfter != "" {
			w.Header().Set("Retry-After", answer.retryAfter)
		}
		w.WriteHeader(answer.status)
		_, _ = w.Write([]byte(answer.body))
	}))
	t.Cleanup(fake.server.Close)
	return fake
}

// answerOperations and answerStorage set the answers of the next queries of the dataset.
func (f *fakeCloudflare) answerOperations(answers ...fakeAnswer) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.operations = answers
}

func (f *fakeCloudflare) answerStorage(answers ...fakeAnswer) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.storage = answers
}

func (f *fakeCloudflare) received() []graphqlCall {
	f.mu.Lock()
	defer f.mu.Unlock()
	return slices.Clone(f.calls)
}

func ok(body string) fakeAnswer {
	return fakeAnswer{status: http.StatusOK, body: body}
}

func failure(status int, body string) fakeAnswer {
	return fakeAnswer{status: status, body: body}
}

// operation is a row of the operations dataset.
type operation struct {
	action   string
	requests float64
}

// operationsBody is an answer of the operations dataset, with one account per list of rows.
func operationsBody(accounts ...[]operation) string {
	var accountsJSON []string
	for _, rows := range accounts {
		var rowsJSON []string
		for _, row := range rows {
			rowsJSON = append(rowsJSON, fmt.Sprintf(`{"dimensions":{"actionType":%q},"sum":{"requests":%v}}`,
				row.action, row.requests))
		}
		accountsJSON = append(accountsJSON, `{"r2OperationsAdaptiveGroups":[`+strings.Join(rowsJSON, ",")+`]}`)
	}
	if accounts == nil {
		accountsJSON = []string{`{"r2OperationsAdaptiveGroups":[]}`}
	}
	return `{"data":{"viewer":{"accounts":[` + strings.Join(accountsJSON, ",") + `]}}}`
}

// point is a row of the storage dataset.
type point struct {
	bucket, datetime          string
	payloadSize, metadataSize float64
}

// storageBody is an answer of the storage dataset, with one account and the points.
func storageBody(points ...point) string {
	rows := make([]string, 0, len(points))
	for _, p := range points {
		rows = append(rows, fmt.Sprintf(
			`{"dimensions":{"bucketName":%q,"datetime":%q},"max":{"payloadSize":%v,"metadataSize":%v}}`,
			p.bucket, p.datetime, p.payloadSize, p.metadataSize))
	}
	return `{"data":{"viewer":{"accounts":[{"r2StorageAdaptiveGroups":[` + strings.Join(rows, ",") + `]}]}}}`
}

const noAccounts = `{"data":{"viewer":{"accounts":[]}}}`

// recordingTimer stands in for retry-go's timer: it records each delay retry-go asks for, and fires at once.
type recordingTimer struct {
	mu     sync.Mutex
	delays []time.Duration
}

func (r *recordingTimer) After(delay time.Duration) <-chan time.Time {
	r.mu.Lock()
	r.delays = append(r.delays, delay)
	r.mu.Unlock()

	fired := make(chan time.Time, 1)
	fired <- time.Now()
	return fired
}

func (r *recordingTimer) requested() []time.Duration {
	r.mu.Lock()
	defer r.mu.Unlock()
	return slices.Clone(r.delays)
}

// useRecordingTimer makes the retries record their delays instead of waiting, until the test ends.
func useRecordingTimer(t *testing.T) *recordingTimer {
	t.Helper()

	timer := &recordingTimer{}
	original := retryTimer
	retryTimer = timer
	t.Cleanup(func() { retryTimer = original })
	return timer
}

// useFakeCloudflare points the client at a fake Cloudflare API until the test ends. The retries don't wait: the
// delays they ask for are recorded by the returned timer.
func useFakeCloudflare(t *testing.T) *fakeCloudflare {
	t.Helper()

	fake := newFakeCloudflare(t)
	fake.timer = useRecordingTimer(t)
	restoreConfig(t)
	CLOUDFLARE_GRAPHQL_ENDPOINT = fake.server.URL + "/client/v4/graphql"
	CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID = "token", "0123abcd"
	CLOUDFLARE_R2_BUCKET_FILTER = ""
	GRAPHQL_RETRY_ATTEMPTS, GRAPHQL_RETRY_DELAY, GRAPHQL_RETRY_MAX_DELAY = 3, 1, 30
	return fake
}

// testNow is a moment in the month of the tests, in Paris, which is UTC+1 in November.
func testNow(t *testing.T) time.Time {
	t.Helper()

	paris, err := time.LoadLocation("Europe/Paris")
	if err != nil {
		t.Fatalf("failed to load Europe/Paris: %v", err)
	}
	return time.Date(2026, time.November, 27, 15, 4, 0, 0, paris)
}

func TestGetCurrentMonthUsageAddsUpTheMonth(t *testing.T) {
	fake := useFakeCloudflare(t)
	fake.answerOperations(ok(operationsBody(
		[]operation{{"PutObject", 10}, {"GetObject", 100}, {"ListObjects", 5}},
		[]operation{{"HeadObject", 7}, {"CopyObject", 1}},
	)))
	fake.answerStorage(ok(storageBody(
		point{"pnls-charts", "2026-11-26T10:00:00Z", 1000, 10},
		point{"pnls-charts", "2026-11-27T10:00:00Z", 2000, 20},
		point{"pnls-backups", "2026-11-27T09:00:00Z", 500, 5},
	)))

	usage, err := newCloudflareClient().getCurrentMonthUsage(testNow(t))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	want := usageMetrics{ClassARequests: 16, ClassBRequests: 107, StorageBytes: 2525}
	if usage != want {
		t.Fatalf("usage = %+v, want %+v", usage, want)
	}
}

func TestGetCurrentMonthUsageQueriesTheMonthOfTheAccount(t *testing.T) {
	fake := useFakeCloudflare(t)

	if _, err := newCloudflareClient().getCurrentMonthUsage(testNow(t)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	calls := fake.received()
	if len(calls) != 2 {
		t.Fatalf("expected two queries, got %d", len(calls))
	}
	for i, wantQuery := range []string{r2OperationsAccountQuery, r2StorageAccountQuery} {
		call := calls[i]
		if call.method != http.MethodPost || call.authorization != "Bearer token" ||
			call.contentType != "application/json" {
			t.Errorf("query %d was sent as %s with %q and %q", i, call.method, call.authorization, call.contentType)
		}
		if call.request.Query != wantQuery {
			t.Errorf("query %d is not the account query:\n%s", i, call.request.Query)
		}
		// The month starts at midnight in Paris on the 1st, which is 23:00 UTC the day before.
		want := map[string]any{
			"accountTag":    "0123abcd",
			"datetimeStart": "2026-10-31T23:00:00Z",
			"datetimeEnd":   "2026-11-27T14:04:00Z",
			"limit":         float64(1000),
		}
		if fmt.Sprint(call.request.Variables) != fmt.Sprint(want) {
			t.Errorf("query %d variables = %v, want %v", i, call.request.Variables, want)
		}
	}
}

func TestGetCurrentMonthUsageWithABucketFilter(t *testing.T) {
	fake := useFakeCloudflare(t)
	CLOUDFLARE_R2_BUCKET_FILTER = "pnls-charts"

	if _, err := newCloudflareClient().getCurrentMonthUsage(testNow(t)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	calls := fake.received()
	if len(calls) != 2 {
		t.Fatalf("expected two queries, got %d", len(calls))
	}
	if calls[0].request.Query != r2OperationsAccountBucketQuery ||
		calls[1].request.Query != r2StorageAccountBucketQuery {
		t.Error("expected the bucket queries")
	}
	for i, call := range calls {
		if call.request.Variables["bucketName"] != "pnls-charts" {
			t.Errorf("query %d bucketName = %v, want pnls-charts", i, call.request.Variables["bucketName"])
		}
	}
}

func TestGetCurrentMonthUsageOnTheFirstOfTheMonth(t *testing.T) {
	fake := useFakeCloudflare(t)
	now := time.Date(2026, time.December, 1, 0, 30, 0, 0, testNow(t).Location())

	if _, err := newCloudflareClient().getCurrentMonthUsage(now); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	variables := fake.received()[0].request.Variables
	if variables["datetimeStart"] != "2026-11-30T23:00:00Z" || variables["datetimeEnd"] != "2026-11-30T23:30:00Z" {
		t.Errorf("expected the first half hour of December, got %v to %v",
			variables["datetimeStart"], variables["datetimeEnd"])
	}
}

func TestGetCurrentMonthUsageStopsAtTheOperationsError(t *testing.T) {
	fake := useFakeCloudflare(t)
	fake.answerOperations(failure(http.StatusForbidden, `{"errors":[{"message":"forbidden"}]}`))

	usage, err := newCloudflareClient().getCurrentMonthUsage(testNow(t))

	if err == nil || !strings.Contains(err.Error(), "status 403") {
		t.Fatalf("expected the operations error, got %v", err)
	}
	if usage != (usageMetrics{}) {
		t.Errorf("expected no usage with the error, got %+v", usage)
	}
	if calls := fake.received(); len(calls) != 1 {
		t.Errorf("expected storage not to be queried, got %d queries", len(calls))
	}
}

func TestGetCurrentMonthUsageReturnsTheStorageError(t *testing.T) {
	fake := useFakeCloudflare(t)
	fake.answerStorage(ok(noAccounts))

	usage, err := newCloudflareClient().getCurrentMonthUsage(testNow(t))

	if err == nil || err.Error() != "no Cloudflare account data returned from storage dataset" {
		t.Fatalf("expected the storage error, got %v", err)
	}
	if usage != (usageMetrics{}) {
		t.Errorf("expected no usage with the error, got %+v", usage)
	}
}

func TestFetchOperationsWithoutAccounts(t *testing.T) {
	fake := useFakeCloudflare(t)
	fake.answerOperations(ok(noAccounts))

	_, _, err := newCloudflareClient().fetchOperations(testNow(t), testNow(t))

	if err == nil || err.Error() != "no Cloudflare account data returned from operations dataset" {
		t.Fatalf("expected the missing account, got %v", err)
	}
}

func TestFetchOperationsWithoutRows(t *testing.T) {
	useFakeCloudflare(t)

	classA, classB, err := newCloudflareClient().fetchOperations(testNow(t), testNow(t))

	if err != nil || classA != 0 || classB != 0 {
		t.Fatalf("expected no operations, got %v, %v, %v", classA, classB, err)
	}
}

func TestFetchStorageUsesTheLatestPointOfEachBucket(t *testing.T) {
	fake := useFakeCloudflare(t)
	// The points come in any order, and the latest point of a bucket can be smaller than earlier ones.
	fake.answerStorage(ok(storageBody(
		point{"pnls-charts", "2026-11-27T10:00:00Z", 300, 3},
		point{"pnls-charts", "2026-11-20T10:00:00Z", 9000, 90},
		point{"pnls-charts", "2026-11-25T10:00:00Z", 5000, 50},
	)))

	storage, err := newCloudflareClient().fetchStorage(testNow(t), testNow(t))

	if err != nil || storage != 303 {
		t.Fatalf("storage = %v, %v, want the latest point, 303 bytes", storage, err)
	}
}

func TestFetchStorageSkipsMalformedPoints(t *testing.T) {
	fake := useFakeCloudflare(t)
	fake.answerStorage(ok(storageBody(
		point{"pnls-charts", "2026-11-27T10:00:00Z", 300, 3},
		point{"pnls-charts", "27/11/2026 11:00", 9000, 90},
		point{"pnls-backups", "", 500, 5},
	)))

	storage, err := newCloudflareClient().fetchStorage(testNow(t), testNow(t))

	if err != nil || storage != 303 {
		t.Fatalf("storage = %v, %v, want only the valid point, 303 bytes", storage, err)
	}
}

func TestFetchStorageWithoutAccounts(t *testing.T) {
	fake := useFakeCloudflare(t)
	fake.answerStorage(ok(noAccounts))

	if _, err := newCloudflareClient().fetchStorage(testNow(t), testNow(t)); err == nil ||
		err.Error() != "no Cloudflare account data returned from storage dataset" {
		t.Fatalf("expected the missing account, got %v", err)
	}
}

func TestStorageQueryReadsTheLatestPointsFirst(t *testing.T) {
	reason := "the storage query reads up to 1000 points of the whole month without orderBy, so once a month has " +
		"more points, the latest point of a bucket can be left out."
	for _, query := range []string{r2StorageAccountQuery, r2StorageAccountBucketQuery} {
		testutil.ExpectFailure(t, reason, func(t testutil.TB) {
			if !strings.Contains(query, "orderBy: [datetime_DESC]") {
				t.Errorf("expected the query to order the points by datetime_DESC:\n%s", query)
			}
		})
	}
}

func TestQuerySendsTheTokenAndTheVariables(t *testing.T) {
	fake := useFakeCloudflare(t)
	var out storageData

	err := newCloudflareClient().query("query { viewer }", map[string]any{"accountTag": "0123abcd"}, &out)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	call := fake.received()[0]
	if call.authorization != "Bearer token" || call.request.Query != "query { viewer }" ||
		call.request.Variables["accountTag"] != "0123abcd" {
		t.Fatalf("unexpected request %+v", call)
	}
}

func TestQueryReturnsTheGraphQLErrors(t *testing.T) {
	fake := useFakeCloudflare(t)
	GRAPHQL_RETRY_ATTEMPTS = 1
	fake.answerStorage(ok(`{"data":null,"errors":[{"message":"unknown field"},{"message":"bad filter"}]}`))
	var out storageData

	err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out)

	if err == nil || err.Error() != "cloudflare graphql error(s): unknown field; bad filter" {
		t.Fatalf("expected the joined GraphQL errors, got %v", err)
	}
}

func TestQueryDoesNotRetryAnswersThatWontChange(t *testing.T) {
	testCases := []struct {
		name   string
		answer fakeAnswer
	}{
		{name: "GraphQL errors", answer: ok(`{"errors":[{"message":"not authorized for that account"}]}`)},
		{name: "invalid JSON", answer: ok(`<html>maintenance</html>`)},
		{name: "unexpected data", answer: ok(`{"data":{"viewer":5}}`)},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			testutil.CaptureLog(t)
			fake := useFakeCloudflare(t)
			GRAPHQL_RETRY_ATTEMPTS = 2
			fake.answerStorage(testCase.answer)
			var out storageData

			if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err == nil {
				t.Fatal("expected an error")
			}

			calls := len(fake.received())
			reason := "query sets retry.RetryIf, which replaces retry-go's check of retry.Unrecoverable, so errors " +
				"marked as unrecoverable are retried."
			testutil.ExpectFailure(t, reason, func(t testutil.TB) {
				if calls != 1 {
					t.Errorf("expected one request, got %d", calls)
				}
			})
		})
	}
}

func TestQueryDoesNotRetryClientErrors(t *testing.T) {
	for _, status := range []int{http.StatusBadRequest, http.StatusUnauthorized, http.StatusForbidden} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			fake := useFakeCloudflare(t)
			fake.answerStorage(failure(status, `{"errors":[{"message":"denied"}]}`))
			var out storageData

			err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out)

			want := fmt.Sprintf(`cloudflare graphql returned status %d: {"errors":[{"message":"denied"}]}`, status)
			if err == nil || err.Error() != want {
				t.Fatalf("error = %v, want %q", err, want)
			}
			if calls := len(fake.received()); calls != 1 {
				t.Errorf("expected one request, got %d", calls)
			}
		})
	}
}

func TestQueryRetriesServerErrors(t *testing.T) {
	logs := testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	fake.answerStorage(
		failure(http.StatusServiceUnavailable, "busy"),
		failure(http.StatusBadGateway, "busy"),
		ok(storageBody(point{"pnls-charts", "2026-11-27T10:00:00Z", 300, 3})),
	)
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err != nil {
		t.Fatalf("expected the third attempt to succeed, got %v", err)
	}

	if calls := len(fake.received()); calls != 3 {
		t.Errorf("expected three requests, got %d", calls)
	}
	if rows := out.Viewer.Accounts[0].R2StorageAdaptiveGroups; len(rows) != 1 || rows[0].Max.PayloadSize != 300 {
		t.Errorf("unexpected data %+v", out)
	}
	for _, want := range []string{"retry attempt 1 due to error", "retry attempt 2 due to error"} {
		if !strings.Contains(logs.String(), want) {
			t.Errorf("expected %q in the log, got:\n%s", want, logs.String())
		}
	}
	if delays := fake.timer.requested(); len(delays) != 2 {
		t.Errorf("expected a delay before each of the two retries, got %v", delays)
	}
}

func TestQueryGivesUpAfterTheAttempts(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	GRAPHQL_RETRY_ATTEMPTS = 2
	fake.answerStorage(failure(http.StatusInternalServerError, "down"))
	var out storageData

	err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out)

	if err == nil || err.Error() != "cloudflare graphql returned status 500: down" {
		t.Fatalf("expected the last error only, got %v", err)
	}
	if calls := len(fake.received()); calls != 2 {
		t.Errorf("expected two requests, got %d", calls)
	}
	// The last attempt isn't followed by a delay.
	if delays := fake.timer.requested(); len(delays) != 1 {
		t.Errorf("expected one delay, got %v", delays)
	}
}

func TestQueryBacksOffExponentiallyUpToTheMaxDelay(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	GRAPHQL_RETRY_ATTEMPTS, GRAPHQL_RETRY_MAX_DELAY = 5, 10
	fake.answerStorage(failure(http.StatusServiceUnavailable, "busy"))
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err == nil {
		t.Fatal("expected the last error")
	}

	want := []time.Duration{2 * time.Second, 4 * time.Second, 8 * time.Second, 10 * time.Second}
	if delays := fake.timer.requested(); !slices.Equal(delays, want) {
		t.Fatalf("delays = %v, want %v, doubling and capped at the 10 second max delay", delays, want)
	}
}

func TestQueryWaitsForRetryAfter(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	// Without the header, the first retry waits 2 seconds.
	fake.answerStorage(
		fakeAnswer{status: http.StatusTooManyRequests, body: "slow down", retryAfter: "7"},
		ok(storageBody()),
	)
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if delays := fake.timer.requested(); !slices.Equal(delays, []time.Duration{7 * time.Second}) {
		t.Fatalf("delays = %v, want the 7 seconds of Retry-After", delays)
	}
}

func TestQueryRetryAfterIsCappedByTheMaxDelay(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	GRAPHQL_RETRY_MAX_DELAY = 5
	fake.answerStorage(
		fakeAnswer{status: http.StatusTooManyRequests, body: "slow down", retryAfter: "120"},
		ok(storageBody()),
	)
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if delays := fake.timer.requested(); !slices.Equal(delays, []time.Duration{5 * time.Second}) {
		t.Fatalf("delays = %v, want the 5 second max delay", delays)
	}
}

func TestQueryUsesTheConfiguredRetryDelay(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	GRAPHQL_RETRY_DELAY = 4
	fake.answerStorage(failure(http.StatusServiceUnavailable, "busy"), ok(storageBody()))
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	delays := fake.timer.requested()

	reason := "the custom retry.DelayType waits 2^n seconds, so CLOUDFLARE_GRAPHQL_RETRY_DELAY_SECONDS is ignored."
	testutil.ExpectFailure(t, reason, func(t testutil.TB) {
		if len(delays) != 1 || delays[0] < 4*time.Second {
			t.Errorf("delays = %v, want the first retry to wait at least the configured 4 seconds", delays)
		}
	})
}

func TestQueryWaitsForRealWithoutATestTimer(t *testing.T) {
	testutil.CaptureLog(t)
	fake := useFakeCloudflare(t)
	// As in production: retry-go's own timer, with the delay capped at 1 second to keep the test short.
	retryTimer, GRAPHQL_RETRY_MAX_DELAY = nil, 1
	fake.answerStorage(failure(http.StatusServiceUnavailable, "busy"), ok(storageBody()))
	var out storageData

	started := time.Now()
	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Only a lower bound: a slow machine can make the wait longer, never shorter.
	if waited := time.Since(started); waited < time.Second {
		t.Fatalf("waited %s before the retry, want the 1 second delay", waited)
	}
}

func TestQueryWhenCloudflareCantBeReached(t *testing.T) {
	useFakeCloudflare(t)
	CLOUDFLARE_GRAPHQL_ENDPOINT = testutil.RefusedURL()
	GRAPHQL_RETRY_ATTEMPTS = 1
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err == nil ||
		!strings.Contains(err.Error(), "connect") {
		t.Fatalf("expected the connection error, got %v", err)
	}
}

func TestQueryWithAnInvalidEndpoint(t *testing.T) {
	useFakeCloudflare(t)
	CLOUDFLARE_GRAPHQL_ENDPOINT = "http://[::1"
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, nil, &out); err == nil ||
		!strings.Contains(err.Error(), "missing ']'") {
		t.Fatalf("expected the invalid URL, got %v", err)
	}
}

func TestQueryWithVariablesThatArentJSON(t *testing.T) {
	fake := useFakeCloudflare(t)
	var out storageData

	if err := newCloudflareClient().query(r2StorageAccountQuery, map[string]any{"bad": func() {}}, &out); err == nil {
		t.Fatal("expected the encoding error")
	}
	if len(fake.received()) != 0 {
		t.Error("expected no request")
	}
}

func TestNewCloudflareClientUsesTheConfig(t *testing.T) {
	useFakeCloudflare(t)

	client := newCloudflareClient()

	if client.endpoint != CLOUDFLARE_GRAPHQL_ENDPOINT || client.token != "token" || client.accountTag != "0123abcd" {
		t.Errorf("unexpected client %+v", client)
	}
	if client.httpClient.Timeout != 30*time.Second {
		t.Errorf("timeout = %s, want 30s", client.httpClient.Timeout)
	}
}

func TestParseRetryAfterHeader(t *testing.T) {
	now := time.Date(2026, time.November, 27, 12, 0, 0, 0, time.UTC)
	testCases := []struct {
		name, header string
		want         time.Duration
		wantOK       bool
	}{
		{name: "empty", header: ""},
		{name: "seconds", header: "120", want: 2 * time.Minute, wantOK: true},
		{name: "seconds with spaces", header: " 5 ", want: 5 * time.Second, wantOK: true},
		{name: "zero", header: "0"},
		{name: "negative", header: "-5"},
		{name: "date in the future", header: "Fri, 27 Nov 2026 12:00:30 GMT", want: 30 * time.Second, wantOK: true},
		{name: "date in the past", header: "Fri, 27 Nov 2026 11:59:00 GMT"},
		{name: "date now", header: "Fri, 27 Nov 2026 12:00:00 GMT"},
		{name: "garbage", header: "soon"},
	}

	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			got, gotOK := parseRetryAfterHeader(testCase.header, now)
			if got != testCase.want || gotOK != testCase.wantOK {
				t.Fatalf("parseRetryAfterHeader(%q) = %s, %v, want %s, %v",
					testCase.header, got, gotOK, testCase.want, testCase.wantOK)
			}
		})
	}
}

func TestIsRetryableHTTPStatus(t *testing.T) {
	testCases := map[int]bool{
		http.StatusOK:                  false,
		http.StatusBadRequest:          false,
		http.StatusUnauthorized:        false,
		http.StatusForbidden:           false,
		http.StatusNotFound:            false,
		http.StatusTooManyRequests:     true,
		http.StatusInternalServerError: true,
		http.StatusBadGateway:          true,
		http.StatusServiceUnavailable:  true,
		http.StatusGatewayTimeout:      true,
	}

	for status, want := range testCases {
		if got := isRetryableHTTPStatus(status); got != want {
			t.Errorf("isRetryableHTTPStatus(%d) = %v, want %v", status, got, want)
		}
	}
}

func TestRetryableHTTPErrorMessage(t *testing.T) {
	err := &retryableHTTPError{statusCode: http.StatusTooManyRequests, body: "slow down", retryAfter: time.Second}

	if err.Error() != "cloudflare graphql returned status 429: slow down" {
		t.Fatalf("Error() = %q", err.Error())
	}
}

func TestClassifyActionType(t *testing.T) {
	testCases := []struct {
		action, want string
	}{
		{action: "PutObject", want: "A"},
		{action: "CopyObject", want: "A"},
		{action: "ListObjects", want: "A"},
		{action: "ListBuckets", want: "A"},
		{action: "CreateMultipartUpload", want: "A"},
		{action: "UploadPart", want: "A"},
		{action: "CompleteMultipartUpload", want: "A"},
		{action: "GetObject", want: "B"},
		{action: "HeadObject", want: "B"},
		{action: "HeadBucket", want: "B"},
		{action: "GetBucketLocation", want: "B"},
		{action: "getobject", want: "B"},
		{action: "", want: "unknown"},
	}

	for _, testCase := range testCases {
		if got := classifyActionType(testCase.action); got != testCase.want {
			t.Errorf("classifyActionType(%q) = %q, want %q", testCase.action, got, testCase.want)
		}
	}
}

func TestClassifyActionTypeFollowsCloudflarePricing(t *testing.T) {
	testCases := []struct {
		action, want, reason string
	}{
		{
			action: "DeleteObject", want: "free",
			reason: "deletes are free on R2, but every action without get/head/read/download counts as Class A.",
		},
		{
			action: "DeleteObjects", want: "free",
			reason: "deletes are free on R2, but every action without get/head/read/download counts as Class A.",
		},
		{
			action: "AbortMultipartUpload", want: "free",
			reason: "aborting an upload is free on R2, but it counts as Class A.",
		},
		{
			action: "UsageSummary", want: "B",
			reason: "UsageSummary is a Class B operation, but it counts as Class A.",
		},
	}

	for _, testCase := range testCases {
		t.Run(testCase.action, func(t *testing.T) {
			testutil.ExpectFailure(t, testCase.reason, func(t testutil.TB) {
				// A free operation must not be counted in either class.
				got := classifyActionType(testCase.action)
				if testCase.want == "free" && (got == "A" || got == "B") ||
					testCase.want != "free" && got != testCase.want {
					t.Errorf("classifyActionType(%q) = %q, want %s", testCase.action, got, testCase.want)
				}
			})
		})
	}
}
