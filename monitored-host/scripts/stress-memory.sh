#!/usr/bin/env bash
set -euo pipefail

DURATION="${DURATION:-180}"
BYTES="${BYTES:-512M}"
WORKERS="${WORKERS:-1}"

stress-ng --vm "$WORKERS" --vm-bytes "$BYTES" --vm-keep --timeout "${DURATION}s" --metrics-brief
