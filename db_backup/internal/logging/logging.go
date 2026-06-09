package logging

import (
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/getsentry/sentry-go"
)

func InitSentry(sentryDSN string, serviceName string) {
	if strings.TrimSpace(sentryDSN) == "" {
		log.Printf("sentry disabled: SENTRY_DSN is empty")
		return
	}

	if strings.TrimSpace(serviceName) == "" {
		serviceName = "db_backup_worker"
	}

	err := sentry.Init(sentry.ClientOptions{
		Dsn:        sentryDSN,
		ServerName: serviceName,
	})
	if err != nil {
		log.Printf("sentry init failed: %v", err)
	}
}

func Fatalf(format string, args ...any) {
	Fatal(fmt.Sprintf(format, args...))
}

func Fatal(msg string) {
	log.Printf("Fatal Error: %s", msg)

	sentry.WithScope(func(scope *sentry.Scope) {
		scope.SetLevel(sentry.LevelFatal)
		sentry.CaptureMessage(msg)
	})

	sentry.Flush(3 * time.Second)
	os.Exit(1)
}
