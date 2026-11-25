.PHONY: lint fmt run test audit audit-fix

fmt:
	golangci-lint fmt

lint:
	golangci-lint run ./...

run:
	go run .

test:
	go test ./...

audit:
	go run golang.org/x/vuln/cmd/govulncheck@v1.10.0 ./...

audit-fix:
	go get -u -t ./...
	go mod tidy
