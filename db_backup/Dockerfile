FROM golang:1.27.4-alpine AS builder

WORKDIR /workspace

# go.mod replaces util-go with ../util-go, which the integration tests use, so the build needs it next to db_backup.
COPY util-go /workspace/util-go
COPY db_backup/go.mod db_backup/go.sum /workspace/db_backup/
WORKDIR /workspace/db_backup
RUN go mod download

COPY db_backup /workspace/db_backup
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/db-backup-worker ./cmd/worker

FROM alpine:3.22

# The base image can lag behind Alpine's security fixes, so the installed packages are upgraded too.
RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates postgresql17-client tzdata

WORKDIR /app
COPY --from=builder /bin/db-backup-worker /usr/local/bin/db-backup-worker
COPY db_backup/workflows ./workflows

ENTRYPOINT ["db-backup-worker"]
