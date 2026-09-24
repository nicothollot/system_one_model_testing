#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ssh -o BatchMode=yes gx10 'test "$(hostname)" = gx10-fbb7 && mkdir -p ~/kairon-page-router'
bash sync-remote.sh
ssh -o BatchMode=yes gx10 'bash -s' <<'REMOTE'
set -euo pipefail
cd ~/kairon-page-router
mkdir -p vendor logs outputs models
python3 -m venv .venv
if [ ! -d vendor/SemIf/.git ]; then
    git clone https://github.com/TheoLeeCJ/SemIf.git vendor/SemIf
fi
git -C vendor/SemIf checkout 23cf1f39fc9534fe81437200959b6dfc7106e45a
.venv/bin/pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu130
.venv/bin/pip install -e 'vendor/SemIf[test]' -r requirements.txt
.venv/bin/pip check
.venv/bin/python download_model.py
.venv/bin/pip freeze > requirements-resolved.txt
REMOTE
