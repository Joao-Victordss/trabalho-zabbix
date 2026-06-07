#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/var/tmp/tp-zabbix}"
SIZE_MB="${SIZE_MB:-2048}"
FILE="$TARGET_DIR/fill-disk-${SIZE_MB}mb.bin"

mkdir -p "$TARGET_DIR"
dd if=/dev/zero of="$FILE" bs=1M count="$SIZE_MB" status=progress
sync
du -h "$FILE"
