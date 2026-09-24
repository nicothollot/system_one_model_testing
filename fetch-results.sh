#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p page-router/outputs page-router/logs
rsync -az gx10:kairon-page-router/outputs/ page-router/outputs/
rsync -az gx10:kairon-page-router/logs/ page-router/logs/
