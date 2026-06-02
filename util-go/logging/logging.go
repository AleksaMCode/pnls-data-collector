package logging

import (
	"log"
	"os"
	"time"

	"github.com/getsentry/sentry-go"
	"gopkg.in/natefinch/lumberjack.v2"
)

func InitLogging(logFile string) {
	log.SetOutput(&lumberjack.Logger{
		Filename:   logFile,
		MaxSize:    1_000, // Max size in MB before rotating
		MaxBackups: 3,
		MaxAge:     28,
		Compress:   true,
	})
}

func InitSentry(sentryDSN string, serviceName string) {
	err := sentry.Init(sentry.ClientOptions{
		Dsn:        sentryDSN,
		ServerName: serviceName,
	})
	if err != nil {
		log.Printf("sentry init failed: %v", err)
	}
	defer sentry.Flush(2 * time.Second)
}

func InitObservability(logFile string, sentryDSN string, serviceName string) {
	InitLogging(logFile)
	InitSentry(sentryDSN, serviceName)
}

func Fatal(msg string) {
	// local rotated file log
	log.Printf("Fatal Error: %s", msg)

	// sentry
	sentry.WithScope(func(scope *sentry.Scope) {
		scope.SetLevel(sentry.LevelFatal)
		sentry.CaptureMessage(msg)
	})
	sentry.Flush(3 * time.Second)
	os.Exit(1)
}
