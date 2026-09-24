#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# No deletion, weights, environments, documents, credentials, or existing services touched.
rsync -az --exclude='.venv/' --exclude='vendor/' --exclude='models/' --exclude='outputs/' --exclude='logs/' --exclude='samples/' --exclude='__pycache__/' --exclude='.pytest_cache/' --exclude='.router.lock' --exclude='.gui.pid' page-router/ gx10:kairon-page-router/
