"""Online setup step only. No document processing or inference."""
import json
import os
from pathlib import Path

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["DO_NOT_TRACK"] = "1"
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parent
model = "Qwen/Qwen3.5-4B"
revision = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
target = root / "models/Qwen3.5-4B"
snapshot_download(model, revision=revision, local_dir=target,
                  allow_patterns=["*.json", "*.safetensors", "*.jinja", "*.txt", "*.model", "LICENSE*"], max_workers=2)
(target / "router-manifest.json").write_text(json.dumps({"model": model, "revision": revision}, indent=2))
print(target)
