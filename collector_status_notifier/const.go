package main

const (
	// Replace with your actual Mattermost webhook URL
	FIREBASE_CREDENTIALS_FILE = "firebase_credentials.json"
	FIREBASE_BASE_PATH        = "/"
	TIMESTAMP_FORMAT          = "2006-01-02 15:04:05.999999"
	// Sleep time between checking devices Firebase status
	FIREBASE_TIMEOUT = 11
	LOG_FILE         = "consumer_status_notifier.log"
	TIMEZONE         = "Europe/Paris"
)

const (
	DEVICE_RPI_1 = "RPI-1"
	DEVICE_RPI_2 = "RPI-2"
	DEVICE_RPI_3 = "RPI-3"
)

var Devices = []string{DEVICE_RPI_1, DEVICE_RPI_2, DEVICE_RPI_3}
