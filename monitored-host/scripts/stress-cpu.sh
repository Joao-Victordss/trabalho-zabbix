#!/usr/bin/env bash
set -euo pipefail

DURATION="${DURATION:-180}"
WORKERS="${WORKERS:-2}"

stress-ng --cpu "$WORKERS" --timeout "${DURATION}s" --metrics-brief
