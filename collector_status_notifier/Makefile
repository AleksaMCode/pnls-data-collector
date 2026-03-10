.PHONY: fmt run test test-coverage test-coverage-view test-coverage-view-browser

fmt:
	golangci-lint fmt

run:
	go run .

test:
	go test ./...

test-coverage:
	go test -coverprofile=coverage ./...

test-coverage-view:
	go tool cover -func=coverage

test-coverage-view-browser:
	go tool cover -html=coverage