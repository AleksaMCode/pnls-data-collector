FROM golang:1.27.4-alpine AS builder

WORKDIR /workspace

COPY util-go /workspace/util-go
COPY firebase_limit_notifier /workspace/firebase_limit_notifier

WORKDIR /workspace/firebase_limit_notifier
RUN go mod download \
    && CGO_ENABLED=0 GOOS=linux go build -o /workspace/bin/firebase-limit-notifier .

FROM alpine:3.22

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

COPY --from=builder /workspace/bin/firebase-limit-notifier /usr/local/bin/firebase-limit-notifier

CMD ["firebase-limit-notifier"]
