FROM golang:1.25.5-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/db-backup-worker ./cmd/worker

FROM alpine:3.22

RUN apk add --no-cache ca-certificates postgresql17-client tzdata

WORKDIR /app
COPY --from=builder /bin/db-backup-worker /usr/local/bin/db-backup-worker
COPY workflows ./workflows

ENTRYPOINT ["db-backup-worker"]
