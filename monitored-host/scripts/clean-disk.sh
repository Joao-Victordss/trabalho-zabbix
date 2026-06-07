#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/var/tmp/tp-zabbix}"

rm -f "$TARGET_DIR"/fill-disk-*.bin
sync
echo "Arquivos temporarios removidos de $TARGET_DIR"
