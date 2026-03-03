//go:build integration

package main

import (
	"context"
	"fmt"
	"io"
	"net/url"
	"strings"
	"testing"

	"github.com/aws/aws-sdk-go-v2/service/s3"
	tc "github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/minio"
	"github.com/testcontainers/testcontainers-go/wait"
)

type r2EnvSnapshot struct {
	accessKey         string
	secretKey         string
	bucketName        string
	cloudflareAccount string
	bucketPublicURL   string
	endpoint          string
}

func snapshotR2Env() r2EnvSnapshot {
	return r2EnvSnapshot{
		accessKey:         R2_ACCESS_KEY,
		secretKey:         R2_SECRET_KEY,
		bucketName:        R2_BUCKET_NAME,
		cloudflareAccount: CLOUDFLARE_ACCOUNT_ID,
		bucketPublicURL:   R2_BUCKET_PUBLIC_URL,
		endpoint:          R2_ENDPOINT,
	}
}

func restoreR2Env(s r2EnvSnapshot) {
	R2_ACCESS_KEY = s.accessKey
	R2_SECRET_KEY = s.secretKey
	R2_BUCKET_NAME = s.bucketName
	CLOUDFLARE_ACCOUNT_ID = s.cloudflareAccount
	R2_BUCKET_PUBLIC_URL = s.bucketPublicURL
	R2_ENDPOINT = s.endpoint
}

func ensureHTTPURL(raw string) string {
	if raw == "" {
		return raw
	}
	if strings.HasPrefix(raw, "http://") || strings.HasPrefix(raw, "https://") {
		return raw
	}
	// testcontainers MinIO may return host:port; AWS SDK needs a full URI.
	return "http://" + raw
}

func TestUploadImageToR2WithMinioTestcontainer(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			panicMsg := fmt.Sprint(r)
			if strings.Contains(strings.ToLower(panicMsg), "rootless docker is not supported on windows") {
				t.Skipf("skipping integration test due to unsupported Docker mode on Windows: %s", panicMsg)
			}
			panic(r)
		}
	}()

	ctx := context.Background()

	minioUser := "minioadmin"
	minioPass := "minioadmin"
	bucketName := "firebase-limit-test"

	container, err := minio.Run(
		ctx,
		"minio/minio:latest",
		minio.WithUsername(minioUser),
		minio.WithPassword(minioPass),
		tc.WithWaitStrategy(wait.ForListeningPort("9000/tcp")),
	)
	if err != nil {
		t.Fatalf("failed to start MinIO container: %v", err)
	}
	t.Cleanup(func() {
		if termErr := container.Terminate(ctx); termErr != nil {
			t.Fatalf("failed to terminate MinIO container: %v", termErr)
		}
	})

	endpoint, err := container.ConnectionString(ctx)
	if err != nil {
		t.Fatalf("failed to get MinIO endpoint: %v", err)
	}
	endpoint = ensureHTTPURL(endpoint)
	if _, err := url.ParseRequestURI(endpoint); err != nil {
		t.Fatalf("invalid MinIO endpoint %q: %v", endpoint, err)
	}

	snapshot := snapshotR2Env()
	t.Cleanup(func() { restoreR2Env(snapshot) })

	R2_ACCESS_KEY = minioUser
	R2_SECRET_KEY = minioPass
	R2_BUCKET_NAME = bucketName
	R2_ENDPOINT = endpoint
	R2_BUCKET_PUBLIC_URL = endpoint

	client := newR2Client()

	_, err = client.CreateBucket(ctx, &s3.CreateBucketInput{
		Bucket: &R2_BUCKET_NAME,
	})
	if err != nil {
		t.Fatalf("failed to create test bucket: %v", err)
	}

	input := []byte("test-image-bytes")
	publicURL, err := uploadImageToR2(input)
	if err != nil {
		t.Fatalf("uploadImageToR2 returned error: %v", err)
	}

	if !strings.HasPrefix(publicURL, R2_BUCKET_PUBLIC_URL+"/"+R2_BUCKET_DIR+"/") {
		t.Fatalf("unexpected public URL format: %s", publicURL)
	}

	objectKey := strings.TrimPrefix(publicURL, R2_BUCKET_PUBLIC_URL+"/")
	obj, err := client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: &R2_BUCKET_NAME,
		Key:    &objectKey,
	})
	if err != nil {
		t.Fatalf("failed to fetch uploaded object: %v", err)
	}
	defer obj.Body.Close()

	got, err := io.ReadAll(obj.Body)
	if err != nil {
		t.Fatalf("failed to read object body: %v", err)
	}

	if string(got) != string(input) {
		t.Fatalf("uploaded object mismatch: got %q, want %q", string(got), string(input))
	}
}
