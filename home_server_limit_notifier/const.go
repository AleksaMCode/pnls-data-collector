package main

const (
	SERVICE_NAME = "Home Server limit notifier"
	LOG_FILE     = "home_server_limit_notifier.log"

	DEFAULT_HTTP_PORT     = "9091"
	DEFAULT_ENDPOINT_PATH = "/check"
	DEFAULT_DISK_MOUNT    = "/"

	BYTES_IN_GB = 1024 * 1024 * 1024
)

var (
	MATTERMOST_WEBHOOK_URL string
	SENTRY_DSN             string
	HTTP_PORT              string
	CHECK_ENDPOINT_PATH    string
	DISK_MOUNT_PATH        string
)
