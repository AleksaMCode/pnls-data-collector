package main

import (
	"bytes"
	"context"
	"fmt"

	"github.com/AleksaMCode/pnls-data-collector/util-go/common"
	"github.com/AleksaMCode/pnls-data-collector/util-go/objectstore"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
)

// r2StoreConfig is the R2 bucket the charts are uploaded to.
func r2StoreConfig() objectstore.Config {
	store := objectstore.R2Config(CLOUDFLARE_ACCOUNT_ID, R2_ENDPOINT)
	store.AccessKey = R2_ACCESS_KEY
	store.SecretKey = R2_SECRET_KEY
	store.Bucket = R2_BUCKET_NAME
	store.PublicURL = R2_BUCKET_PUBLIC_URL
	return store
}

// chartUploadOptions are the settings of the uploaded charts.
var chartUploadOptions = objectstore.UploadOptions{
	ContentType: "image/png",
	ACL:         types.ObjectCannedACLPublicRead,
}

// uploadImageToR2 uploads the chart and returns its public link. A store that can't be set up is returned as an error,
// so the report is still sent, without the chart.
func uploadImageToR2(image []byte) (string, error) {
	store, err := objectstore.New(context.TODO(), r2StoreConfig())
	if err != nil {
		return "", err
	}

	objectKey := fmt.Sprintf("%s/firebase-usage-%d.png", R2_BUCKET_DIR, common.GetTimeNow(TIMEZONE).Unix())
	return store.Upload(context.TODO(), objectKey, bytes.NewReader(image), chartUploadOptions)
}
