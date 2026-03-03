#!/bin/bash

pushd collector_status_notifier
golangci-lint fmt
popd

pushd firebase_limit_notifier
golangci-lint fmt
popd

pushd util-go
golangci-lint fmt
popd
