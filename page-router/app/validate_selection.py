"""Validate policies against a real saved run with all inference entry points blocked."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from app import selection, settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    before_bytes = args.run.read_bytes()
    raw = json.loads(before_bytes)
    before = selection.digest(raw)
    assert len(raw["pages"]) == 40 and all(selection.valid_scores(p) for p in raw["pages"])
    truth_text = "12,20,26,32,40"  # Temporary software-test labels, not a claimed ground-truth annotation.
    truth = selection.parse_ground_truth(truth_text, 40)
    direct = selection.select_pages(raw["pages"], settings.preset("benchmark_direct"), truth)
    recall = selection.select_pages(raw["pages"], settings.preset("production_recall"), truth)
    weighted = selection.select_pages(raw["pages"], {**settings.defaults(), "mode": "weighted", "preset": "custom"}, truth)
    sweep = selection.threshold_sweep(raw["pages"], truth)
    assert selection.digest(raw) == before
    folder = args.run.parent / "selection-validation"
    folder.mkdir(exist_ok=True)
    exported = selection.export_selection(raw, direct, folder)
    assert selection.digest(json.loads(Path(exported["json"]).read_text())) == before

    from streamlit.testing.v1 import AppTest
    from app import engine
    import semif_phase1.shared
    import semif_phase1.direct
    def forbidden(*args, **kwargs):
        raise AssertionError("Selection GUI attempted inference")
    with tempfile.TemporaryDirectory(prefix="kairon-policy-validation-") as temp, \
         patch.object(settings, "SETTINGS_PATH", Path(temp) / "router_settings.json"), \
         patch.object(settings, "PRESETS_PATH", Path(temp) / "router_presets.json"), \
         patch.object(engine, "run", forbidden), patch.object(engine.Router, "load", forbidden), \
         patch.object(engine.Router, "classify", forbidden), patch.object(semif_phase1.shared, "score_shared", forbidden), \
         patch.object(semif_phase1.direct, "score", forbidden):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "gui.py"))
        app.run(timeout=30)
        app.selectbox(key="saved_run").set_value(args.run.resolve()).run(timeout=30)
        next(b for b in app.button if b.label == "Open Saved Run").click().run(timeout=30)
        assert not app.exception, list(app.exception)
        assert app.session_state.current_selection["final_selected_pages"] == direct["final_selected_pages"]
        app.number_input(key="policy_requested_data_threshold").set_value(1.0).run(timeout=30)
        strict = app.session_state.current_selection["final_selected_pages"]
        assert strict != direct["final_selected_pages"]
        app.text_input(key="ground_truth_" + before[:16]).set_value(truth_text).run(timeout=30)
        expected = selection.benchmark_metrics(strict, truth, 40)
        assert app.session_state.current_selection["benchmark_metrics"] == expected
        app.selectbox(key="preset_to_load").set_value("production_recall").run(timeout=30)
        next(b for b in app.button if b.label == "Load Preset").click().run(timeout=30)
        assert app.session_state.current_selection["final_selected_pages"] == recall["final_selected_pages"]
        app.selectbox(key="policy_mode").set_value("weighted").run(timeout=30)
        app.multiselect(key="graph_series").set_value(["requested_data", "overall_relevance", "routing_score"]).run(timeout=30)
        app.selectbox(key="sweep_series").set_value("routing_score").run(timeout=30)
        assert not app.exception, list(app.exception)
        assert selection.digest(app.session_state.result) == before
        assert app.session_state.policy_settings["weighted_threshold"] == .55
        next(b for b in app.button if b.label == "Save Settings").click().run(timeout=30)
        assert "ground_truth" not in settings.SETTINGS_PATH.read_text()
        reopened = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "gui.py")).run(timeout=30)
        assert reopened.session_state.policy_settings == app.session_state.policy_settings
    assert args.run.read_bytes() == before_bytes
    report = {"source_run": str(args.run), "source_file_sha256": hashlib.sha256(before_bytes).hexdigest(),
              "raw_model_result_sha256": before, "raw_result_unchanged": True, "inference_entry_points_blocked": True,
              "gui_saved_run_opened": True, "gui_selection_changes_without_inference": True,
              "settings_survive_new_gui_session": True, "temporary_labels_only": truth,
              "benchmark_metrics_are_software_validation_not_accuracy_claims": True,
              "direct_final_pages": direct["final_selected_pages"], "recall_final_pages": recall["final_selected_pages"],
              "weighted_final_pages": weighted["final_selected_pages"], "direct_metrics": direct["benchmark_metrics"],
              "threshold_sweep_rows": len(sweep["rows"]), "test_selection_export": exported}
    (folder / "validation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
