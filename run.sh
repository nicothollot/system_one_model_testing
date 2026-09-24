#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ssh -o BatchMode=yes gx10 'test "$(hostname)" = gx10-fbb7 && bash ~/kairon-page-router/serve.sh'
echo "Open http://localhost:8507 — keep this terminal open for the private SSH tunnel."
exec ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -N -L 127.0.0.1:8507:127.0.0.1:8507 gx10
