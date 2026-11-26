package containers

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	tc "github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/minio"
	"github.com/testcontainers/testcontainers-go/wait"
)

const (
	// SiloImage is the S3-compatible server that stands in for Cloudflare R2. Silo is a maintained fork of MinIO.
	SiloImage = "pgsty/silo:RELEASE.2026-11-12T00-00-00Z"
	// SiloAccessKey and SiloSecretKey are the keys the tests use for Silo, in place of the R2 keys.
	SiloAccessKey = "minioadmin"
	SiloSecretKey = "minioadmin"
)

// Silo is a running Silo server.
type Silo struct {
	// Endpoint is the server's URL, e.g. http://localhost:32768, for R2_ENDPOINT. It needs path-style requests.
	Endpoint string
}

var silo shared[*Silo]

// StartSilo returns the Silo server shared by the tests of this binary, and starts it on first use.
func StartSilo(t *testing.T) *Silo {
	t.Helper()

	return silo.get(t, "Silo", func(ctx context.Context) (*Silo, error) {
		container, err := minio.Run(ctx, SiloImage,
			minio.WithUsername(SiloAccessKey),
			minio.WithPassword(SiloSecretKey),
			// The port opens before the server accepts requests, so wait for its health check.
			tc.WithWaitStrategy(wait.ForHTTP("/minio/health/live").WithPort("9000/tcp")),
		)
		if err != nil {
			return nil, err
		}
		address, err := container.ConnectionString(ctx)
		if err != nil {
			return nil, err
		}
		return &Silo{Endpoint: "http://" + strings.TrimPrefix(address, "http://")}, nil
	})
}

// S3Client returns a client for the server with the test keys, to set up buckets and check what a test uploaded.
func (s *Silo) S3Client() *s3.Client {
	return s3.New(s3.Options{
		BaseEndpoint: aws.String(s.Endpoint),
		Region:       "auto",
		Credentials:  credentials.NewStaticCredentialsProvider(SiloAccessKey, SiloSecretKey, ""),
		UsePathStyle: true,
	})
}

// CreateBucket creates a new empty bucket named after the prefix, and returns its name.
func (s *Silo) CreateBucket(t *testing.T, prefix string) string {
	t.Helper()

	name := prefix + "-" + randomSuffix(t)
	if _, err := s.S3Client().CreateBucket(t.Context(), &s3.CreateBucketInput{Bucket: &name}); err != nil {
		t.Fatalf("failed to create the bucket %s: %v", name, err)
	}
	return name
}

// GetObject returns the content and the content type of an object.
func (s *Silo) GetObject(t *testing.T, bucket, key string) (content []byte, contentType string) {
	t.Helper()

	object, err := s.S3Client().GetObject(t.Context(), &s3.GetObjectInput{Bucket: &bucket, Key: &key})
	if err != nil {
		t.Fatalf("failed to get %s/%s: %v", bucket, key, err)
	}
	defer object.Body.Close()

	content, err = io.ReadAll(object.Body)
	if err != nil {
		t.Fatalf("failed to read %s/%s: %v", bucket, key, err)
	}
	return content, aws.ToString(object.ContentType)
}

// ListKeys returns the keys of the objects in a bucket.
func (s *Silo) ListKeys(t *testing.T, bucket string) []string {
	t.Helper()

	output, err := s.S3Client().ListObjectsV2(t.Context(), &s3.ListObjectsV2Input{Bucket: &bucket})
	if err != nil {
		t.Fatalf("failed to list %s: %v", bucket, err)
	}
	keys := make([]string, 0, len(output.Contents))
	for _, object := range output.Contents {
		keys = append(keys, aws.ToString(object.Key))
	}
	return keys
}

// randomSuffix keeps the names of buckets and databases unique between tests sharing a container.
func randomSuffix(t *testing.T) string {
	t.Helper()

	suffix := make([]byte, 4)
	if _, err := rand.Read(suffix); err != nil {
		t.Fatalf("failed to make a random name: %v", err)
	}
	return hex.EncodeToString(suffix)
}
