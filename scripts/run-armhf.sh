#!/usr/bin/env bash
set -euo pipefail
export QEMU_LD_PREFIX=${QEMU_LD_PREFIX:-/usr/arm-linux-gnueabihf}
exec qemu-arm "$@"
