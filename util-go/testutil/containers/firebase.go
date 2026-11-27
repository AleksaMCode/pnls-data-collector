package containers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"path/filepath"
	"strings"
	"testing"
	"time"

	tc "github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"

	"github.com/AleksaMCode/pnls-data-collector/util-go/testutil"
)

const (
	// FirebaseEmulatorImage is the image built from tests/integration/firebase_emulator. The Python integration tests
	// build the same image under the same name, so Docker builds it once for both.
	FirebaseEmulatorImage = "pnls-firebase-database-emulator:test"
	firebaseDatabasePort  = "9000/tcp"
	firebaseAuthPort      = "9099/tcp"
	// emulatorToken is the access token the emulator accepts as an admin, which isn't checked against any rules.
	emulatorToken = "owner"
)

// FirebaseEmulator is a running Firebase Realtime Database and Authentication emulator.
type FirebaseEmulator struct {
	// Host is the database emulator's address, localhost:<port>.
	Host string
	// AuthHost is the Authentication emulator's address, localhost:<port>.
	AuthHost string
}

var firebaseEmulator shared[*FirebaseEmulator]

// StartFirebaseEmulator returns the emulator shared by the tests of this binary. On first use it builds the image,
// which takes a few minutes the first time and is cached by Docker after that, and starts the emulator.
func StartFirebaseEmulator(t *testing.T) *FirebaseEmulator {
	t.Helper()

	return firebaseEmulator.get(t, "the Firebase emulator", func(ctx context.Context) (*FirebaseEmulator, error) {
		repo, tag, _ := strings.Cut(FirebaseEmulatorImage, ":")
		container, err := tc.Run(ctx, "",
			tc.WithDockerfile(tc.FromDockerfile{
				Context:   filepath.Join(repoRoot(), "tests", "integration", "firebase_emulator"),
				Repo:      repo,
				Tag:       tag,
				KeepImage: true,
			}),
			tc.WithExposedPorts(firebaseDatabasePort, firebaseAuthPort),
			tc.WithWaitStrategy(wait.ForLog("All emulators ready").WithStartupTimeout(3*time.Minute)),
		)
		if err != nil {
			return nil, err
		}

		host, err := container.Host(ctx)
		if err != nil {
			return nil, err
		}
		// The Go SDK takes an emulator URL only as host:port?ns=<name>, and an IP address doesn't parse in that form.
		if ip := net.ParseIP(host); ip != nil {
			if !ip.IsLoopback() {
				return nil, fmt.Errorf("the Docker host %s is an IP address the Firebase SDK can't use", host)
			}
			host = "localhost"
		}
		databasePort, err := container.MappedPort(ctx, firebaseDatabasePort)
		if err != nil {
			return nil, err
		}
		authPort, err := container.MappedPort(ctx, firebaseAuthPort)
		if err != nil {
			return nil, err
		}
		return &FirebaseEmulator{
			Host:     net.JoinHostPort(host, databasePort.Port()),
			AuthHost: net.JoinHostPort(host, authPort.Port()),
		}, nil
	})
}

// FirebaseDatabase is one database of the emulator, used by one test.
type FirebaseDatabase struct {
	emulator  *FirebaseEmulator
	Namespace string
}

// CreateDatabase returns a new empty database named after the prefix. The emulator creates it on first write.
func (e *FirebaseEmulator) CreateDatabase(t *testing.T, prefix string) *FirebaseDatabase {
	t.Helper()

	return &FirebaseDatabase{emulator: e, Namespace: prefix + "-" + randomSuffix(t)}
}

// URL is the database URL for the services' FIREBASE_DATABASE_URL, in the emulator format host:port?ns=<name>.
// The SDK sends every request of a client made with this URL to the emulator, with the emulator's admin token.
func (d *FirebaseDatabase) URL() string {
	return d.emulator.Host + "?ns=" + d.Namespace
}

// CredentialsFile returns a service account for the services' credentials file. The SDK reads it, but with an
// emulator URL it never uses it, so its token URL is unreachable on purpose: a real token request fails the test.
func (d *FirebaseDatabase) CredentialsFile(t *testing.T) string {
	t.Helper()

	return testutil.WriteServiceAccount(t, testutil.RefusedURL()+"/token")
}

// Set writes the value at the path, replacing what was there, like a collector writing its data.
func (d *FirebaseDatabase) Set(t *testing.T, path string, value any) {
	t.Helper()

	body, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("failed to encode the value for %s: %v", path, err)
	}
	d.do(t, http.MethodPut, path, body, nil)
}

// Get reads the value at the path into target.
func (d *FirebaseDatabase) Get(t *testing.T, path string, target any) {
	t.Helper()

	d.do(t, http.MethodGet, path, nil, target)
}

func (d *FirebaseDatabase) do(t *testing.T, method, path string, body []byte, target any) {
	t.Helper()

	url := fmt.Sprintf("http://%s/%s.json?ns=%s", d.emulator.Host, strings.Trim(path, "/"), d.Namespace)
	request, err := http.NewRequestWithContext(t.Context(), method, url, bytes.NewReader(body))
	if err != nil {
		t.Fatalf("failed to make the request: %v", err)
	}
	request.Header.Set("Authorization", "Bearer "+emulatorToken)

	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("%s %s failed: %v", method, path, err)
	}
	defer response.Body.Close()
	reply, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("failed to read the reply of %s %s: %v", method, path, err)
	}
	if response.StatusCode != http.StatusOK {
		t.Fatalf("%s %s answered %s: %s", method, path, response.Status, reply)
	}
	if target != nil {
		if err := json.Unmarshal(reply, target); err != nil {
			t.Fatalf("failed to decode %s: %v", path, err)
		}
	}
}
