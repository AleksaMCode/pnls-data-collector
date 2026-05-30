#!/bin/bash

pushd collector_status_notifier
make fmt
popd

pushd firebase_limit_notifier
make fmt
popd

pushd util-go
make fmt
popd

pushd cloudflare_limit_notifier
make fmt
popd