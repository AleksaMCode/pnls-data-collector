FROM golang:1.25.5-alpine AS builder

WORKDIR /workspace

COPY util-go /workspace/util-go
COPY collector_status_notifier /workspace/collector_status_notifier

WORKDIR /workspace/collector_status_notifier
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /workspace/bin/collector-status-notifier .

FROM alpine:3.22

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

COPY --from=builder /workspace/bin/collector-status-notifier /usr/local/bin/collector-status-notifier

CMD ["collector-status-notifier"]
