"""Real CUDA smoke test; no inference mocks. Run once before starting the GUI."""
import json
from pathlib import Path
import socket

import pymupdf
from openpyxl import Workbook

from app.data import validate_scores
from app.engine import ROOT, Router, run


def fixtures(folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True, parents=True)
    doc = pymupdf.open()
    for text in [
        "SITE SURVEY\nThe requested tree survey counted 142 oak trees and 37 birch trees.\nCounts were taken in the northern study area on 12 June 2025.",
        "SURVEY METHODOLOGY\nA tree is included if its trunk diameter exceeds 10 cm.\nThe oak count excludes dead trees. See note 1 for the survey boundary.\nNote 1: The northern study area ends at the river.",
        "CAFETERIA MENU\nMonday: vegetable soup and bread. Tuesday: pasta and salad.\nMeals are served between noon and 2 pm. Please return trays after eating.",
        "",
    ]:
        page = doc.new_page()
        page.insert_text((50, 70), text)
    doc.save(folder / "tiny.pdf")
    doc.close()
    (folder / "instructions.json").write_text(json.dumps({"requested_fields": ["oak_tree_count", "survey_date"], "instructions": "Find the oak tree count and survey date. Include definitions and exclusions needed to interpret the count."}))
    book = Workbook()
    sheet = book.active
    sheet.title = "Field definitions"
    sheet.append(["Field", "Definition"])
    sheet.append(["oak_tree_count", "Number of living oak trees in the northern study area"])
    sheet.append(["survey_date", "Date on which the field survey was conducted"])
    book.save(folder / "reference.xlsx")
    return folder


def main():
    # The inference smoke test must succeed with Python TCP connections blocked.
    original_connect = socket.socket.connect
    def offline_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError(f"Smoke test forbids network connections: {address}")
        return original_connect(sock, address)
    socket.socket.connect = offline_connect
    folder = fixtures(ROOT / "samples")
    router = Router()
    with router.lock:
        router.load(print)
        from semif_phase1.direct import score
        row = {"id": "direct-smoke", "state": "There are 142 oak trees in the study area.",
               "question": "Does the evidence state an oak tree count?",
               "options": [{"id": "yes", "description": "Yes"}, {"id": "no", "description": "No"}]}
        direct = score(router.model, router.tokenizer, row, router.metadata)
        assert len(direct["probabilities"]) == 2
        assert abs(sum(direct["probabilities"]) - 1) < 1e-9
        (ROOT / "outputs").mkdir(exist_ok=True)
        (ROOT / "outputs/direct-smoke.json").write_text(json.dumps(direct, indent=2))
        print("Direct probabilities", direct["probabilities"])
    result = run(router, "tiny.pdf", (folder / "tiny.pdf").read_bytes(), (folder / "instructions.json").read_bytes(),
                 (folder / "reference.xlsx").read_bytes(), print)
    assert len(result["pages"]) == 4
    for page in result["pages"]:
        validate_scores(page["scores"])
    assert result["pages"][-1]["needs_visual_or_ocr_review"]
    assert result["run"]["vllm_processes_unchanged"]
    print(json.dumps({k: v for k, v in result["run"].items() if not k.startswith("memory")}, indent=2))


if __name__ == "__main__":
    main()
