package storage

import (
	"context"
	"fmt"
	"os"
	"strings"

	"db_backup/internal/config"

	"github.com/aws/aws-sdk-go-v2/aws"
	awsConfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

type ObjectUploader interface {
	UploadFile(ctx context.Context, key string, filePath string) (string, error)
}

type R2Uploader struct {
	cfg    config.Config
	client *s3.Client
}

func NewR2Uploader(cfg config.Config) (*R2Uploader, error) {
	awsCfg, err := awsConfig.LoadDefaultConfig(
		context.Background(),
		awsConfig.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(cfg.R2AccessKey, cfg.R2SecretKey, ""),
		),
		awsConfig.WithRegion("auto"),
	)
	if err != nil {
		return nil, err
	}

	client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
		endpoint := cfg.R2Endpoint
		if endpoint == "" {
			endpoint = fmt.Sprintf("https://%s.r2.cloudflarestorage.com", cfg.CloudflareAccountID)
		}
		o.BaseEndpoint = aws.String(endpoint)
		if cfg.R2Endpoint != "" {
			o.UsePathStyle = true
		}
	})

	return &R2Uploader{
		cfg:    cfg,
		client: client,
	}, nil
}

func (u *R2Uploader) UploadFile(ctx context.Context, key string, filePath string) (string, error) {
	f, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	_, err = u.client.PutObject(ctx, &s3.PutObjectInput{
		Bucket:      aws.String(u.cfg.R2BucketName),
		Key:         aws.String(key),
		Body:        f,
		ContentType: aws.String("application/gzip"),
	})
	if err != nil {
		return "", err
	}

	publicURL := strings.TrimRight(u.cfg.R2BucketPublicURL, "/") + "/" + key
	return publicURL, nil
}
