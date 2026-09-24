"""Render and simulator checks; no model inference in these unit tests."""
from pathlib import Path
import pytest

from streamlit.testing.v1 import AppTest

from app import data


def test_gui_initial():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "gui.py")).run(timeout=20)
    assert not app.exception
    assert app.button[0].disabled


def test_gui_results_and_simulation(tmp_path, monkeypatch):
    from app import engine
    def forbidden(*args, **kwargs):
        raise AssertionError("Simulator must not call inference")
    monkeypatch.setattr(engine, "run", forbidden)
    pages = []
    for number, yes in enumerate([.2, .8, .3], 1):
        pages.append({"page": number, "scores": {key: {"yes": yes, "no": 1 - yes} for key in data.QUESTIONS},
                      "characters": 100, "tokens": 25, "approx_tokens": 25, "classification_seconds": .1,
                      "needs_visual_or_ocr_review": False, "text_extraction_warning": None, "extracted_text": "example"})
    result = {"run": {"pdf": "test.pdf", "total_pages": 3, "model": "test fixture", "backend": "fixture",
                      "device": "none", "status": "completed", "log": "test.log"},
              "inputs": {"constructed_extraction_objective": "example"}, "pages": pages, "threshold_summary": data.thresholds(pages)}
    data.export(result, tmp_path, "gui-test")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "gui.py"))
    app.session_state["result"] = result
    app.run(timeout=20)
    assert not app.exception
    app.slider[0].set_value(.75).run()
    assert not app.exception
    app.toggle[0].set_value(True).run()
    assert not app.exception


@pytest.mark.parametrize("scored", [0, 1])
def test_invalid_runs_hide_reduction_statistics(tmp_path, scored):
    pages = [{"page": n + 1, "scores": {key: {"yes": .8, "no": .2} for key in data.QUESTIONS} if n < scored else None,
              "characters": 100, "approx_tokens": 25, "classification_seconds": .1, "needs_visual_or_ocr_review": False,
              "needs_router_review": n >= scored, "text_extraction_warning": None, "extracted_text": "text"} for n in range(3)]
    result = {"run": {"pdf": "failed.pdf", "total_pages": 3, "model": "fixture", "backend": "fixture", "device": "none",
                      "status": "partial", "log": "test.log"}, "pages": pages,
              "inputs": {"compiled_routing_objective": "example"}, "threshold_summary": {"0.50": {"count": 0}}}
    data.export(result, tmp_path, "failed")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "gui.py"))
    app.session_state["result"] = result
    app.run(timeout=20)
    assert not app.exception
    assert not app.slider and not app.toggle
    assert any("DOES NOT mean zero relevant" in error.value for error in app.error)
    assert any(f"{scored} / 3 successfully scored" in message.value for message in app.markdown)
