package main

import "time"

const (
	SERVICE_NAME              = "Collector status notifier"
	FIREBASE_CREDENTIALS_FILE = "firebase_credentials.json"
	FIREBASE_BASE_PATH        = "/"
	TIMESTAMP_FORMAT          = "2006-01-02 15:04:05.999999"
	// COLLECTOR_TIMEOUT is an idle time (in minutes) between checking devices status
	COLLECTOR_TIMEOUT = 5 * time.Minute
	// FIREABASE_TIMEOUT is time in seconds between checking device's Firebase heartbeat
	FIREABASE_TIMEOUT = 11 * time.Minute
	// DATADOG_TIMEOUT is time in seconds between checking device's Datadog heartbeat
	DATADOG_TIMEOUT = 30 * time.Second
	LOG_FILE        = "consumer_status_notifier.log"
	TIMEZONE        = "Europe/Paris"
)

const (
	DEVICE_RPI_1 = "RPI-1"
	DEVICE_RPI_2 = "RPI-2"
	DEVICE_RPI_3 = "RPI-3"
)

var (
	MATTERMOST_WEBHOOK_URL   string
	FIREBASE_DATABASE_URL    string
	SENTRY_DSN               string
	DATADOG_API_KEY          string
	DATADOG_APP_KEY          string
	DATADOG_HEARTBEAT_METRIC string
	DATADOG_HOST             string
	REDIS_URL                string
	REDIS_PORT               string
	REDIS_PASSWORD           string
	REDIS_DB                 string
)

var Devices = []string{DEVICE_RPI_1, DEVICE_RPI_2, DEVICE_RPI_3}
