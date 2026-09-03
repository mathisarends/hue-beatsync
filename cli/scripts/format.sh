#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
gofmt -w $(find cmd internal -name '*.go' -not -name 'oas_*_gen.go')
