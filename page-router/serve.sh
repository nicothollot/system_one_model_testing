#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
export CUDA_VISIBLE_DEVICES=0 TOKENIZERS_PARALLELISM=false
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
mkdir -p logs outputs
if curl --silent --fail http://127.0.0.1:8507/_stcore/health >/dev/null; then
    echo "Router GUI already available at remote 127.0.0.1:8507"
    exit 0
fi
nohup .venv/bin/python -m streamlit run gui.py --server.address=127.0.0.1 --server.port=8507 > logs/gui.log 2>&1 < /dev/null &
echo "$!" > .gui.pid
for attempt in $(seq 1 30); do
    if curl --silent --fail http://127.0.0.1:8507/_stcore/health >/dev/null; then
        echo "Router GUI ready on GX10 port 8507"
        exit 0
    fi
    sleep 1
done
echo "GUI failed to start; inspect ~/kairon-page-router/logs/gui.log" >&2
exit 1
