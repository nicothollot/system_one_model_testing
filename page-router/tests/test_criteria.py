"""Prompt plumbing/provenance tests, not fabricated semantic model predictions."""
import copy
import json
from pathlib import Path

from app import criteria, data, preparation, selection, settings


class Tokenizer:
    def encode(self, value, **kwargs):
        return value.split()

    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages)


def test_criterion_specific_options_and_versions():
    assert criteria.PROMPT_VERSION == "direct-options-v2"
    assert criteria.CRITERIA_VERSION == "semantic-equivalence-v2"
    assert set(criteria.OPTIONS) == set(criteria.QUESTIONS)
    assert len({o['description'] for options in criteria.OPTIONS.values() for o in options}) == 10
    assert all([o['id'] for o in options] == ['yes', 'no'] for options in criteria.OPTIONS.values())
    assert 'synonyms count' in criteria.QUESTIONS['requested_data']
    assert 'nearby totals' in criteria.QUESTIONS['requested_data']


def test_prepared_prompts_and_export_preserve_exact_criteria(tmp_path):
    pages = [{"page": 1, "extracted_text": "A plain text page", "needs_visual_or_ocr_review": False}]
    preparation.prepare_pages(Tokenizer(), pages, "Requested target")
    page = pages[0]
    assert criteria.versions(page) == criteria.versions({'prompt_version': criteria.PROMPT_VERSION, 'classifier_criteria_version': criteria.CRITERIA_VERSION})
    for key, row in zip(criteria.QUESTIONS, page['classifier_rows']):
        assert row['question'] == criteria.QUESTIONS[key]
        assert row['options'] == criteria.OPTIONS[key]
        assert criteria.QUESTIONS[key] in page['exact_prompts'][key]
        assert all(option['description'] in page['exact_prompts'][key] for option in criteria.OPTIONS[key])
    raw = {'run': criteria.versions(page), 'inputs': {'compiled_routing_objective': 'Requested target'}, 'pages': pages}
    # Failed/unscored exports must preserve exact wording, too.
    page.update(characters=17, approx_tokens=4, text_extraction_warning=None)
    data.export(raw, tmp_path, 'criteria')
    loaded = json.loads((tmp_path/'criteria.json').read_text())
    assert loaded['run']['classifier_criteria_version'] == criteria.CRITERIA_VERSION
    assert loaded['pages'][0]['classification_options'] == criteria.OPTIONS
    assert loaded['pages'][0]['classification_questions'] == criteria.QUESTIONS


def test_defaults_and_production_rescues():
    benchmark = settings.preset('benchmark_direct')
    production = settings.preset('production_recall')
    assert settings.defaults()['requested_data_threshold'] == benchmark['requested_data_threshold'] == production['requested_data_threshold'] == .70
    assert benchmark['neighbor_radius'] == 0
    assert not benchmark['always_include_ocr_review'] and not benchmark['always_include_router_review']
    assert production['overall_relevance_threshold'] == production['supporting_context_threshold'] == .95
    assert production['cross_reference_threshold'] == .97
    assert production['secondary_min_overall'] == .70
    assert production['financial_table_threshold'] == .98 and production['financial_table_min_overall'] == .75
    assert production['neighbor_radius'] == 1
    assert production['always_include_ocr_review'] and production['always_include_router_review']
    assert not benchmark['financial_table_enabled'] and not production['financial_table_enabled']
    settings.validate({**benchmark, 'requested_data_threshold': .99})


def test_legacy_versions_and_immutable_post_inference_labels(tmp_path):
    from test_selection import page
    raw = {'run': {}, 'inputs': {'compiled_routing_objective': 'Original objective'}, 'pages': [page(1, .8), page(2, .2)]}
    original = copy.deepcopy(raw)
    assert criteria.versions(raw['run']) == {'prompt_version': 'direct-options-v1', 'classifier_criteria_version': 'legacy-v1'}
    policy = selection.select_pages(raw['pages'], settings.defaults(), [1])
    paths = selection.export_selection(raw, policy, tmp_path)
    assert selection.model_result(json.loads(Path(paths['json']).read_text())) == raw == original
    assert 'ground_truth' not in json.dumps(raw)
    source = (Path(__file__).parents[1]/'gui.py').read_text()
    assert 'not directly interchangeable' in source and 'Saved classifier versions' in source


def test_startup_and_gui_share_resident_router(monkeypatch):
    from app import runtime
    runtime.resident_router.cache_clear()
    sentinel = object()
    monkeypatch.setattr(runtime, 'Router', lambda: sentinel)
    try:
        assert runtime.resident_router() is sentinel
        assert runtime.resident_router() is sentinel
    finally:
        runtime.resident_router.cache_clear()
