package main

import (
	"bytes"
	"context"
	"fmt"

	common "github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/logging"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

func getR2Endpoint() string {
	if R2_ENDPOINT != "" {
		return R2_ENDPOINT
	}
	return fmt.Sprintf("https://%s.r2.cloudflarestorage.com", CLOUDFLARE_ACCOUNT_ID)
}

func newR2Client() *s3.Client {
	cfg, err := config.LoadDefaultConfig(
		context.TODO(),
		config.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider(
				R2_ACCESS_KEY,
				R2_SECRET_KEY,
				"",
			),
		),
		config.WithRegion("auto"), // Required by SDK but not used by R2
	)
	if err != nil {
		logging.Fatal(err.Error())
		return nil
	}

	client := s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(getR2Endpoint())
		// MinIO and most local S3-compatible test endpoints require path-style URLs.
		if R2_ENDPOINT != "" {
			o.UsePathStyle = true
		}
	})
	return client
}

func uploadImageToR2(image []byte) (string, error) {
	client := newR2Client()
	now := common.GetTimeNow(TIMEZONE)

	objectKey := fmt.Sprintf(
		"%s/firebase-usage-%d.png",
		R2_BUCKET_DIR,
		now.Unix(),
	)

	_, err := client.PutObject(context.TODO(), &s3.PutObjectInput{
		Bucket:      &R2_BUCKET_NAME,
		Key:         &objectKey,
		Body:        bytes.NewReader(image),
		ContentType: aws.String("image/png"),
		ACL:         "public-read",
	})
	if err != nil {
		return "", err
	}

	publicURL := fmt.Sprintf(
		"%s/%s",
		R2_BUCKET_PUBLIC_URL,
		objectKey,
	)

	return publicURL, nil
}
