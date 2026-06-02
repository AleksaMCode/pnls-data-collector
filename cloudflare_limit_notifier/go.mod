module climnot

go 1.25.5

require (
	github.com/AleksaMCode/pnls-data-collector/util-go v0.0.0
	github.com/joho/godotenv v1.5.1
	golang.org/x/text v0.34.0
)

require (
	github.com/getsentry/sentry-go v0.46.2 // indirect
	golang.org/x/sys v0.41.0 // indirect
	gopkg.in/natefinch/lumberjack.v2 v2.2.1 // indirect
)

replace github.com/AleksaMCode/pnls-data-collector/util-go => ../util-go
