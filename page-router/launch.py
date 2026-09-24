"""Launch GUI, optionally running a private three-input manifest first.

The manifest is a list of {pdf, json, xlsx} paths. No evaluation labels are
accepted. The same Router stays resident for subsequent GUI analyses.
"""
import argparse
import json
from pathlib import Path
from app.engine import run
from app.runtime import resident_router


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-manifest", type=Path)
    args = parser.parse_args()
    if args.benchmark_manifest:
        manifest = json.loads(args.benchmark_manifest.read_text())
        for entry in manifest:
            if set(entry) != {"pdf", "json", "xlsx"}:
                raise ValueError("Benchmark manifest accepts only PDF, instructions JSON and reference XLSX paths")
            paths = {k: Path(v) for k, v in entry.items()}
            result = run(resident_router(), paths["pdf"].name, paths["pdf"].read_bytes(), paths["json"].read_bytes(),
                         paths["xlsx"].read_bytes(), progress=lambda message: print(message, flush=True),
                         input_names={k: p.name for k, p in paths.items()})
            print(json.dumps({"exports": result["run"]["exports"], "status": result["run"]["status"]}), flush=True)
    from streamlit.web import bootstrap
    bootstrap.run(str(Path(__file__).with_name("gui.py")), False, [],
                  {"server.address": "127.0.0.1", "server.port": 8507, "browser.gatherUsageStats": False})


if __name__ == "__main__":
    main()
