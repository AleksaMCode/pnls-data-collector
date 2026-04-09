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
	switch {
	case hasBucket:
		return r2OperationsAccountBucketQuery
	default:
		return r2OperationsAccountQuery
	}
}

func selectStorageQuery(hasBucket bool) string {
	switch {
	case hasBucket:
		return r2StorageAccountBucketQuery
	default:
		return r2StorageAccountQuery
	}
}
