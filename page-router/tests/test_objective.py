import json
from types import SimpleNamespace

import pytest

from app import data
from app.engine import Router
from app.objective import compile_objective
from app.preparation import prepare_pages
from app.regression import synthetic_inputs


def test_eighty_fields_are_compiled_and_deduplicated():
    _, raw, workbook = synthetic_inputs()
    instructions, reference = data.parse_json(raw), data.parse_xlsx(workbook)
    compiled = compile_objective(instructions, reference)
    assert compiled == compile_objective(instructions, reference)
    assert compiled["requested_field_count"] == compiled["compiled_field_count"] == 80
    assert compiled["xlsx_duplicates_removed"] == 80
    result = compiled["compiled_routing_objective"]
    for entry in instructions["entries"]:
        assert result.count(entry["header"]) == 1
    assert "Note 11 - Research measurements:" in result
    assert "only completed projects count" in result
    assert "Report only the answer" not in result
    assert "If absent" not in result
    assert "Match the requested fiscal quarter" not in result
    assert len(result) < len(json.dumps(instructions)) / 4


def test_reference_definitions_and_unknown_semantics_survive():
    reference = [{"sheet": "defs", "rows": [[{"cell": "A1", "value": "Field"}, {"cell": "B1", "value": "Definition"}],
                  [{"cell": "A2", "value": "Tree count"}, {"cell": "B2", "value": "Only living trees above 10 cm diameter"}]]}]
    source = {"entries": [{"header": "Tree count", "source_section": "Survey", "denomination": "Integer",
                          "instruction": "Exclude birch trees. If absent, leave blank.", "custom_constraint": "Northern boundary"}]}
    result = compile_objective(source, reference)
    objective = result["compiled_routing_objective"]
    assert result["compiled_field_count"] == 1
    for value in ["Survey:", "Tree count [Integer]", "Exclude birch trees", "Northern boundary", "Only living trees above 10 cm"]:
        assert value in objective
    assert "If absent" not in objective


@pytest.fixture
def tokenizer():
    from app.engine import MODEL_PATH, offline
    offline()
    if not MODEL_PATH.exists():
        pytest.skip("Exact tokenizer regression requires the installed local model snapshot")
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True)


def test_real_tokenizer_budget_for_eighty_fields(tokenizer):
    pdf, raw, workbook = synthetic_inputs()
    pages = data.preprocess(pdf)
    objective = data.objective(data.parse_json(raw), data.parse_xlsx(workbook))
    budget = prepare_pages(tokenizer, pages, objective)
    assert budget["routing_objective_tokens"] <= 3072
    assert budget["available_token_headroom_min"] > 3000
    assert not budget["input_preparation_errors"]
    assert all(len(p["exact_prompt_tokens"]) == 5 and p["page_text_tokens"] > 0 for p in pages)


def test_oversized_objective_fails_before_model_loading(tokenizer, tmp_path, monkeypatch):
    import threading
    from app import engine
    pdf, _, workbook = synthetic_inputs()
    source = {"fields": [f"Required full field {i} " + "meaningful constraint " * 200 for i in range(80)]}
    router = SimpleNamespace(lock=threading.Lock(), get_tokenizer=lambda: tokenizer, model=None, load_seconds=0)
    def forbidden(*args, **kwargs):
        pytest.fail("Input preparation failure must not load the model or classify")
    router.load = router.classify = forbidden
    monkeypatch.setattr(engine, "ROOT", tmp_path)
    monkeypatch.setattr(engine, "guard", lambda *a: None)
    result = engine.run(router, "too-large.pdf", pdf, json.dumps(source).encode(), workbook)
    assert result["run"]["status"] == "FAILED_INPUT_PREPARATION"
    assert result["run"]["prompt_version"] == "direct-options-v2"
    assert result["run"]["classifier_criteria_version"] == "semantic-equivalence-v2"
    assert result["run"]["scored_pages"] == result["run"]["model_forward_seconds"] == 0
    assert "compaction" in result["run"]["classification_error"]
    assert result["threshold_summary"] == {}
    assert all(p["needs_router_review"] and not p["needs_visual_or_ocr_review"] for p in result["pages"])
    assert result["inputs"]["instructions_json"] == source
    assert all(field in result["inputs"]["compiled_routing_objective"] for field in source["fields"])


@pytest.mark.parametrize("original_ocr", [False, True])
def test_classifier_valueerror_never_changes_ocr(original_ocr, monkeypatch):
    import semif_phase1.shared
    import app.engine
    def fail(*args, **kwargs):
        raise ValueError("context or probability validation error")
    monkeypatch.setattr(semif_phase1.shared, "score_shared", fail)
    monkeypatch.setattr(app.engine, "guard", lambda *args: None)
    router = SimpleNamespace(model=None, tokenizer=None, metadata={}, before={"swap_used_bytes": 0})
    page = {"classifier_rows": [], "needs_visual_or_ocr_review": original_ocr}
    Router.classify(router, page)
    assert page["needs_visual_or_ocr_review"] is original_ocr
    assert page["needs_router_review"] and page["classification_error"]
