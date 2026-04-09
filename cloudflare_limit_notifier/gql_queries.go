package main

import _ "embed"

//go:embed gql/r2_operations_account.gql
var r2OperationsAccountQuery string

//go:embed gql/r2_operations_account_bucket.gql
var r2OperationsAccountBucketQuery string

//go:embed gql/r2_storage_account.gql
var r2StorageAccountQuery string

//go:embed gql/r2_storage_account_bucket.gql
var r2StorageAccountBucketQuery string

func selectOperationsQuery(hasBucket bool) string {
	if hasBucket {
		return r2OperationsAccountBucketQuery
	} else {
		return r2OperationsAccountQuery
	}
}

func selectStorageQuery(hasBucket bool) string {
	if hasBucket {
		return r2StorageAccountBucketQuery
	} else {
		return r2StorageAccountQuery
	}
}
