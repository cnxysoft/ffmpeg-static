#!/usr/bin/env bash
set -euo pipefail
export QEMU_LD_PREFIX=${QEMU_LD_PREFIX:-/usr/arm-linux-gnueabihf}
# Ubuntu 22.04's qemu-user cannot reliably emulate Go's ARM signal preemption.
# This affects test execution only; it does not change the compiled binaries.
export GODEBUG="${GODEBUG:+$GODEBUG,}asyncpreemptoff=1"
exec qemu-arm "$@"
