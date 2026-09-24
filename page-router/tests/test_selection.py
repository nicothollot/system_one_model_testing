import copy
import csv
import json
import pytest
from app import data, selection, settings


def page(n, requested=.1, overall=.1, context=.1, cross=.1, financial=.1, **extra):
    values = [overall, requested, context, financial, cross]
    return {"page": n, "scores": {key: {"yes": p, "no": 1-p} for key, p in zip(data.QUESTIONS, values)},
            "characters": 100, "approx_tokens": 25, "classification_seconds": .1, "text_extraction_warning": None,
            "needs_visual_or_ocr_review": False, "extracted_text": "unchanged evidence", **extra}


def test_requested_data_inclusive_and_raw_unchanged():
    pages = [page(1, .60, .1), page(2, .599, .99)]
    before = copy.deepcopy(pages)
    result = selection.select_pages(pages, settings.defaults())
    assert result["final_selected_pages"] == [1]
    assert result["selection_reasons"]["1"] == ["requested_data_threshold"]
    assert pages == before


def test_recall_or_gates_financial_disabled_and_multiple_reasons():
    pages = [page(1, .6, .9, .9, .95, 1), page(2, .1, .54, 1, 1), page(3, .1, .55, .9),
             page(4, .1, .55, .1, .95), page(5, .1, .65, .1, .1, .97)]
    policy = settings.preset("production_recall")
    policy["neighbor_radius"] = 0
    result = selection.select_pages(pages, policy)
    assert result["final_selected_pages"] == [1, 3, 4]
    assert set(result["selection_reasons"]["1"]) == {"requested_data_threshold", "overall_relevance_threshold", "supporting_context_rescue", "cross_reference_rescue"}
    policy["financial_table_enabled"] = True
    assert selection.select_pages(pages, policy)["final_selected_pages"] == [1, 3, 4, 5]
    policy["financial_table_min_overall"] = .66
    assert 5 not in selection.select_pages(pages, policy)["final_selected_pages"]


def test_weighted_score_no_silent_normalization():
    policy = settings.defaults()
    policy.update(mode="weighted", requested_data_weight=1.3)
    p = page(1, .5, .2, .3, .4, 1)
    expected = 1.3*.5 + .2*.2 + .1*.3 + .05*.4
    result = selection.select_pages([p], policy)
    assert result["routing_scores"]["1"] == pytest.approx(expected)
    assert result["weight_sum"] == pytest.approx(1.65)
    assert result["selection_reasons"]["1"] == ["weighted_score"]
    policy["weighted_threshold"] = 1
    assert not selection.select_pages([p], policy)["final_selected_pages"]


@pytest.mark.parametrize("radius,expected", [(0, [1, 4]), (1, [1, 2, 3, 4, 5]), (2, [1, 2, 3, 4, 5])])
def test_neighbors_boundaries_and_reasons(radius, expected):
    pages = [page(n, .8 if n in (1, 4) else .1) for n in range(1, 6)]
    policy = settings.defaults()
    policy["neighbor_radius"] = radius
    result = selection.select_pages(pages, policy)
    assert result["raw_selected_pages"] == [1, 4]
    assert result["final_selected_pages"] == expected
    assert set(result["neighbor_added_pages"]) == set(expected) - {1, 4}
    if radius == 2:
        assert result["selection_reasons"]["2"] == ["neighbor_of_page_1", "neighbor_of_page_4"]


def test_manual_review_and_incomplete_run_are_not_fake_metrics():
    pages = [page(1, needs_visual_or_ocr_review=True), page(2, scores=None),
             page(3, needs_visual_or_ocr_review=True, text_extraction_status="ok")]
    policy = settings.preset("production_recall")
    policy["neighbor_radius"] = 0
    result = selection.select_pages(pages, policy, [1])
    assert result["model_selected_pages"] == []
    assert result["raw_selected_pages"] == [1, 2]
    assert result["selection_reasons"] == {"1": ["ocr_review"], "2": ["router_review"]}
    assert result["benchmark_metrics"] is None and result["page_reduction_percent"] is None
    assert not result["statistics_valid"]
    with pytest.raises(ValueError):
        selection.threshold_sweep(pages, [1])


def test_settings_persistence_presets_and_reset(tmp_path):
    path, presets = tmp_path / "router_settings.json", tmp_path / "presets.json"
    initial = settings.load(path)
    assert initial["mode"] == "requested_data_only" and initial["requested_data_threshold"] == .6
    custom = {**initial, "preset": "custom", "requested_data_threshold": .72, "neighbor_radius": 2}
    settings.save(custom, path)
    assert settings.load(path) == custom
    assert settings.preset("custom", custom) == custom
    settings.save_preset("My policy", custom, presets)
    loaded = settings.preset("saved:My policy", custom_presets=settings.load_presets(presets))
    assert loaded["requested_data_threshold"] == .72
    with pytest.raises(ValueError):
        settings.save_preset("My policy", initial, presets)
    assert settings.preset("production_recall")["neighbor_radius"] == 1
    assert settings.reset(path) == settings.defaults() == settings.load(path)
    with pytest.raises(ValueError):
        settings.save({**custom, "ground_truth": [1, 2]}, path)
    assert "ground_truth" not in path.read_text()


@pytest.mark.parametrize("value,expected", [("12,20,26,32,40", [12,20,26,32,40]), ("12, 20, 26, 32, 40", [12,20,26,32,40]),
                                            ("1-3, 2, 40", [1,2,3,40]), ("", None), ("[]", [])])
def test_ground_truth_parsing(value, expected):
    assert selection.parse_ground_truth(value, 40) == expected


@pytest.mark.parametrize("value", ["0", "41", "-1", "3-1", "one", "1.5"])
def test_bad_ground_truth(value):
    with pytest.raises(ValueError):
        selection.parse_ground_truth(value, 40)


def test_confusion_matrix_and_f_scores():
    result = selection.benchmark_metrics([1,2,4], [1,2,3], 6)
    assert [result[k] for k in ("true_positives", "false_positives", "true_negatives", "false_negatives")] == [2,1,2,1]
    assert result["false_negative_pages"] == [3] and result["false_positive_pages"] == [4]
    for key in ("precision", "recall", "specificity", "f1", "f2"):
        assert result[key] == pytest.approx(2/3)
    assert result["false_negative_rate"] == result["false_positive_rate"] == pytest.approx(1/3)
    asymmetric = selection.benchmark_metrics([1,4], [1,2,3], 5)
    assert asymmetric["f1"] == pytest.approx(2/5)
    assert asymmetric["f2"] == pytest.approx(5/14)
    empty = selection.benchmark_metrics([], [], 5)
    assert empty["recall"] is None and empty["precision"] is None and empty["f1"] is None
    assert empty["specificity"] == 1


def test_threshold_sweep_is_standalone_and_does_not_change_settings():
    pages = [page(1, .8), page(2, .6), page(3, .2)]
    policy = settings.preset("production_recall")
    original = copy.deepcopy(policy)
    sweep = selection.threshold_sweep(pages, [1,2], settings=policy)
    assert len(sweep["rows"]) == 101
    assert sweep["rows"][0]["selected_pages"] == 3 and sweep["rows"][-1]["selected_pages"] == 0
    assert sweep["highest_threshold_full_recall"] == .6
    assert sweep["highest_f1_threshold"] == sweep["highest_f2_threshold"] == .6
    assert policy == original
    for series in selection.SERIES:
        assert len(selection.threshold_sweep(pages, [1], series, policy)["rows"]) == 101


def test_export_preserves_whole_raw_result_and_all_probability_precision(tmp_path):
    raw = {"run": {"pdf": "test.pdf"}, "inputs": {"instructions_json": {"field": "private"}}, "pages": [page(1, .943218123456789), page(2, .1)]}
    before = copy.deepcopy(raw)
    policy = selection.select_pages(raw["pages"], settings.defaults(), [1])
    paths = selection.export_selection(raw, policy, tmp_path)
    loaded = json.loads(open(paths["json"]).read())
    assert selection.model_result(loaded) == raw == before
    assert selection.digest(loaded) == selection.digest(raw) == loaded["selection"]["source_model_result_sha256"]
    assert loaded["selection"]["benchmark_ground_truth"] == [1]
    with open(paths["csv"]) as handle:
        rows = list(csv.DictReader(handle))
    assert float(rows[0]["requested_data_yes"]) == .943218123456789
    assert rows[0]["selected"] == "True" and rows[1]["selected"] == "False"
    assert "benchmark_ground_truth" not in loaded["inputs"]
