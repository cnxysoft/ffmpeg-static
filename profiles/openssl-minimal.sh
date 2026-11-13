#!/usr/bin/env bash
# Run from an OpenSSL source tree. Pass the target, install paths, and C flags.
set -euo pipefail

exec perl Configure \
  no-shared no-tests no-apps no-docs \
  no-quic no-module no-engine no-legacy no-comp \
  "$@"
