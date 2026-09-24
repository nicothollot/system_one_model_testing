"""Offline, real CUDA regression: small fixture, 80 fields, then original benchmark."""
import argparse
import csv
import io
import json
from pathlib import Path

import pymupdf
from openpyxl import Workbook

from app import data
from app.engine import ROOT, Router, run
from app.smoke import fixtures


BOILERPLATE = ("Match the requested fiscal quarter, fiscal year, or balance-sheet date exactly; "
               "do not substitute a prior-year amount, forecast, commitment, segment total, or a different financial definition. "
               "Report only the answer and cite its page and supporting line. If absent, leave blank.")


def synthetic_inputs():
    entries = []
    for index in range(80):
        name = f"Q4 2026 research metric {index:02d} ($m)"
        instruction = f"Use the Note {index // 2 + 1} - Research measurements section and report the explicitly stated {name}. {BOILERPLATE}"
        if index in (20, 60):
            instruction += " Exclude proposed projects; only completed projects count."
        entries.append({"header": name, "instruction": instruction, "denomination": "In $ million", "method": "extracted", "formula": ""})
    book = Workbook()
    book.active.append([e["header"] for e in entries])
    buffer = io.BytesIO()
    book.save(buffer)
    doc = pymupdf.open()
    for number in range(4):
        page = doc.new_page()
        page.insert_text((40, 50), f"RESEARCH REPORT PAGE {number + 1}\nNote {number + 1} - Research measurements\n"
                         "Q4 2026 research spending was 12 million dollars.\nOnly completed projects count; proposed projects are excluded.\n"
                         "This section contains definitions and supporting evidence for the reported measures.")
    pdf = doc.tobytes()
    doc.close()
    return pdf, json.dumps({"entries": entries}).encode(), buffer.getvalue()


def validate(result):
    metrics = result["run"]
    assert metrics["status"] == "COMPLETED", metrics.get("classification_error")
    assert metrics["scored_pages"] == metrics["total_pages"]
    assert metrics["model_forward_seconds"] > 0
    assert metrics["available_token_headroom_min"] >= 256
    persisted = json.loads(Path(metrics["exports"]["json"]).read_text())
    with open(metrics["exports"]["csv"], newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(result["pages"]) == len(persisted["pages"])
    for page, row in zip(result["pages"], rows):
        data.validate_scores(page["scores"])
        assert page["classification_status"] == "scored" and not page["needs_router_review"]
        assert page["needs_visual_or_ocr_review"] == (page["text_extraction_status"] != "ok")
        assert page["semif_timing"]["prefill_seconds"] > 0
        for key, raw in zip(data.QUESTIONS, page["raw_distributions"]):
            assert page["exact_prompt_tokens"][key] == raw["input_tokens"]
        for key, distribution in page["scores"].items():
            for option, probability in distribution.items():
                assert float(row[f"{key}_{option}"]) == probability
    assert metrics["vllm_processes_unchanged"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--instructions", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(args.source_run.read_text())
    payloads = [args.pdf.read_bytes(), args.instructions.read_bytes(), args.reference.read_bytes()]
    for key, payload in zip(("pdf", "json", "xlsx"), payloads):
        assert data.fingerprint(payload) == original["inputs"]["sha256"][key], f"Original {key} mismatch"
    router = Router()
    small = fixtures(ROOT / "samples")
    results = []
    results.append(run(router, "tiny.pdf", (small / "tiny.pdf").read_bytes(), (small / "instructions.json").read_bytes(),
                       (small / "reference.xlsx").read_bytes(), print))
    validate(results[-1])
    results.append(run(router, "synthetic-80-fields.pdf", *synthetic_inputs(), progress=print))
    validate(results[-1])
    assert results[-1]["inputs"]["routing_objective_compilation"]["requested_field_count"] == 80
    real = run(router, args.pdf.name, *payloads, progress=print,
               input_names={"pdf": args.pdf.name, "json": args.instructions.name, "xlsx": args.reference.name})
    validate(real)
    assert real["run"]["scored_pages"] == real["run"]["total_pages"] == 40
    assert real["inputs"]["routing_objective_compilation"]["requested_field_count"] == 80
    assert [p["extracted_text"] for p in real["pages"]] == [p["extracted_text"] for p in original["pages"]]
    results.append(real)
    summary = {"source_run": str(args.source_run), "original_input_hashes_match": True, "original_page_text_matches": True,
               "runs": [{k: r["run"][k] for k in ("pdf", "status", "scored_pages", "total_pages", "routing_objective_tokens",
                         "exact_prompt_tokens_min", "exact_prompt_tokens_max", "available_token_headroom_min", "classification_seconds",
                         "model_forward_seconds", "average_page_seconds", "median_page_seconds", "vllm_processes_unchanged", "exports")} for r in results]}
    (ROOT / "outputs" / "regression-validation.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
