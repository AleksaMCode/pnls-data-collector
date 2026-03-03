.PHONY: fmt run test test-integration test-coverage test-coverage-view

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