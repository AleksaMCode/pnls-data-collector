.PHONY: run test test-integration test-coverage test-coverage-view test-coverage-view-browser audit audit-fix

fmt:
	golangci-lint fmt
	
run:
	go run .

test:
	go test ./...

test-integration:
	go test -tags integration ./...

test-coverage:
	go test -coverprofile=coverage ./...

test-coverage-view:
	go tool cover -func=coverage

test-coverage-view-browser:
	go tool cover -html=coverage

audit:
	go run golang.org/x/vuln/cmd/govulncheck@v1.10.0 ./...

audit-fix:
	go get -u -t ./...
	go mod tidy
