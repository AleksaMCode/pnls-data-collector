package firebase

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"testing"
)

func TestGetFirebaseClientMissingCredentialsFatal(t *testing.T) {
	if os.Getenv("TEST_MISSING_CREDS_FATAL") == "1" {
		GetFirebaseClient(context.Background(), "definitely-missing-creds.json", "https://example.firebaseio.com")
		return
	}

	cmd := exec.Command(os.Args[0], "-test.run=TestGetFirebaseClientMissingCredentialsFatal")
	cmd.Env = append(os.Environ(), "TEST_MISSING_CREDS_FATAL=1")

	err := cmd.Run()
	if err == nil {
		t.Fatal("expected process to exit with non-zero status")
	}

	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		t.Fatalf("expected *exec.ExitError, got %T (%v)", err, err)
	}
}
