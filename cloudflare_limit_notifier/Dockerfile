FROM golang:1.25.5-alpine AS builder

WORKDIR /app

COPY cloudflare_limit_notifier/go.mod cloudflare_limit_notifier/go.sum ./cloudflare_limit_notifier/
COPY util-go ./util-go

WORKDIR /app/cloudflare_limit_notifier
RUN go mod download

COPY cloudflare_limit_notifier ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/cloudflare-limit-notifier .

FROM alpine:3.22

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY --from=builder /bin/cloudflare-limit-notifier /usr/local/bin/cloudflare-limit-notifier
COPY cloudflare_limit_notifier/.env /app/.env

ENTRYPOINT ["cloudflare-limit-notifier"]
