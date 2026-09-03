#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
golangci-lint run
go vet ./...
go test -race ./...
