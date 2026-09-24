"""Render and simulator checks; no model inference in these unit tests."""
from pathlib import Path
import pytest

from streamlit.testing.v1 import AppTest

from app import data


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    from app import settings
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "router_settings.json")
    monkeypatch.setattr(settings, "PRESETS_PATH", tmp_path / "router_presets.json")


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
    app.number_input(key="policy_requested_data_threshold").set_value(.75).run()
    assert not app.exception
    app.selectbox(key="policy_neighbor_radius").set_value(1).run()
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


def test_settings_labels_presets_saved_results_never_infer(tmp_path, monkeypatch):
    import copy
    from app import engine, selection, settings
    from test_selection import page
    def forbidden(*args, **kwargs):
        pytest.fail("Post-inference UI attempted model inference")
    monkeypatch.setattr(engine, "run", forbidden)
    monkeypatch.setattr(engine.Router, "load", forbidden)
    monkeypatch.setattr(engine.Router, "classify", forbidden)
    raw = {"run": {"pdf": "saved.pdf", "model": "fixture", "backend": "fixture", "device": "none", "status": "completed"},
           "inputs": {"compiled_routing_objective": "UNCHANGED REQUEST"}, "pages": [page(1,.8), page(2,.1), page(3,.6)]}
    before = copy.deepcopy(raw)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "gui.py"))
    app.session_state["result"] = raw
    app.run(timeout=20)
    assert not app.exception
    assert app.session_state.current_selection["final_selected_pages"] == [1,3]
    app.number_input(key="policy_requested_data_threshold").set_value(.9).run()
    assert app.session_state.current_selection["final_selected_pages"] == []
    key = "ground_truth_" + selection.digest(raw)[:16]
    app.text_input(key=key).set_value("1,3").run()
    assert not app.exception
    assert app.session_state.current_selection["benchmark_metrics"]["false_negative_pages"] == [1,3]
    app.selectbox(key="sweep_series").set_value("routing_score").run()
    assert app.session_state.policy_settings["requested_data_threshold"] == .9
    app.button[ next(i for i,b in enumerate(app.button) if b.label == "Save Settings") ].click().run()
    assert settings.load()["requested_data_threshold"] == .9
    assert "ground_truth" not in settings.SETTINGS_PATH.read_text()
    app.selectbox(key="preset_to_load").set_value("production_recall").run()
    next(b for b in app.button if b.label == "Load Preset").click().run()
    assert app.session_state.policy_settings["neighbor_radius"] == 1
    assert app.session_state.current_selection["final_selected_pages"] == [1,2,3]
    app.number_input(key="policy_requested_data_weight").set_value(1.3).run()
    assert any("do not sum" in w.value for w in app.warning)
    next(b for b in app.button if b.label == "Reset to Defaults").click().run()
    assert not app.exception
    assert app.session_state.policy_settings == settings.defaults()
    assert app.session_state.result == before
    assert app.session_state.current_selection["benchmark_ground_truth"] == [1,3]
