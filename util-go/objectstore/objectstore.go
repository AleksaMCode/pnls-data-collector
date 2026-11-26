// Package objectstore uploads to S3-compatible object storage: Cloudflare R2, which the services use today, AWS S3, or
// Silo in the tests. A Store is one bucket, with the public URL its objects are served from.
package objectstore

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
)

// R2Region is the region to use with Cloudflare R2. R2 ignores it, but the SDK needs one.
const R2Region = "auto"

// Config describes the store and the bucket to upload to.
type Config struct {
	// Endpoint is the store's URL, e.g. R2Endpoint(accountID) or http://localhost:9000.
	Endpoint string
	// AccessKey and SecretKey are the store's static keys.
	AccessKey string
	SecretKey string
	// Region is the store's region: R2Region for Cloudflare R2, or a real region such as eu-central-1 for AWS S3.
	Region string
	// UsePathStyle puts the bucket in the path (endpoint/bucket/key) instead of the host name (bucket.endpoint/key).
	// Most local S3-compatible servers, such as Silo and MinIO, need it.
	UsePathStyle bool
	// Bucket is the bucket the store uploads to.
	Bucket string
	// PublicURL is the base of the links the uploads return, e.g. the bucket's public r2.dev URL.
	PublicURL string
}

// R2Endpoint is the S3 API endpoint of a Cloudflare account's R2 storage.
func R2Endpoint(accountID string) string {
	return fmt.Sprintf("https://%s.r2.cloudflarestorage.com", accountID)
}

// R2Config returns the connection settings for Cloudflare R2: the account's endpoint, or customEndpoint when it is
// set, e.g. a local server in tests, which then gets path-style requests. The caller adds the keys and the bucket.
func R2Config(accountID, customEndpoint string) Config {
	if customEndpoint != "" {
		return Config{Endpoint: customEndpoint, Region: R2Region, UsePathStyle: true}
	}
	return Config{Endpoint: R2Endpoint(accountID), Region: R2Region}
}

// UploadOptions are the optional settings of an upload. An empty field isn't sent.
type UploadOptions struct {
	// ContentType is the object's media type, e.g. image/png.
	ContentType string
	// ACL is the object's canned ACL, e.g. types.ObjectCannedACLPublicRead.
	ACL types.ObjectCannedACL
}

// Uploader uploads objects and returns their public links. The services depend on it, so their tests can use a fake.
type Uploader interface {
	// Upload stores the body under the key.
	Upload(ctx context.Context, key string, body io.Reader, opts UploadOptions) (string, error)
	// UploadFile streams the file at path to the key.
	UploadFile(ctx context.Context, key, path string, opts UploadOptions) (string, error)
}

// Store uploads to one bucket.
type Store struct {
	cfg    Config
	client *s3.Client
}

var _ Uploader = (*Store)(nil)

// New makes a store. The other SDK settings, such as retries, come from the usual AWS environment variables.
func New(ctx context.Context, cfg Config) (*Store, error) {
	switch {
	case cfg.Endpoint == "":
		return nil, errors.New("object store endpoint is empty")
	case cfg.Region == "":
		return nil, errors.New("object store region is empty")
	case cfg.Bucket == "":
		return nil, errors.New("object store bucket is empty")
	}

	awsCfg, err := awsconfig.LoadDefaultConfig(
		ctx,
		awsconfig.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(cfg.AccessKey, cfg.SecretKey, "")),
		awsconfig.WithRegion(cfg.Region),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to load the object store config: %w", err)
	}

	client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(cfg.Endpoint)
		o.UsePathStyle = cfg.UsePathStyle
	})
	return &Store{cfg: cfg, client: client}, nil
}

// Bucket is the bucket the store uploads to.
func (s *Store) Bucket() string {
	return s.cfg.Bucket
}

// PublicURL is the link to the object with the key.
func (s *Store) PublicURL(key string) string {
	return strings.TrimRight(s.cfg.PublicURL, "/") + "/" + key
}

// Upload stores the body under the key and returns the object's public link.
func (s *Store) Upload(ctx context.Context, key string, body io.Reader, opts UploadOptions) (string, error) {
	input := &s3.PutObjectInput{
		Bucket: aws.String(s.cfg.Bucket),
		Key:    aws.String(key),
		Body:   body,
		ACL:    opts.ACL,
	}
	if opts.ContentType != "" {
		input.ContentType = aws.String(opts.ContentType)
	}

	if _, err := s.client.PutObject(ctx, input); err != nil {
		return "", fmt.Errorf("failed to upload %s to the bucket %s: %w", key, s.cfg.Bucket, err)
	}
	return s.PublicURL(key), nil
}

// UploadFile streams the file at path to the key and returns the object's public link.
func (s *Store) UploadFile(ctx context.Context, key, path string, opts UploadOptions) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("failed to open %s for the upload: %w", path, err)
	}
	defer file.Close()

	return s.Upload(ctx, key, file, opts)
}
