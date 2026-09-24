import csv
import io
import json

import pymupdf
import pytest
from openpyxl import Workbook

from app import data


def test_json():
    assert data.parse_json(b'{"fields":["arbitrary"]}')["fields"] == ["arbitrary"]
    for raw in [b'{', b'null', b'{}', b'{"a":NaN}', b'\xff']:
        with pytest.raises(ValueError):
            data.parse_json(raw)


def test_xlsx():
    book = Workbook()
    book.active.append(["arbitrary field", "a definition"])
    book.create_sheet("other").append(["=1+2", 7])
    raw = io.BytesIO()
    book.save(raw)
    parsed = data.parse_xlsx(raw.getvalue())
    assert parsed[0]["rows"][0][1]["value"] == "a definition"
    assert parsed[1]["rows"][0][0]["value"] == "=1+2"
    assert "cached_value" in parsed[1]["rows"][0][0]
    assert "arbitrary field" in data.objective({"fields": ["custom"]}, parsed)
    with pytest.raises(ValueError):
        data.parse_xlsx(b"bad")


def test_pdf():
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "Some extracted text " * 8)
    doc.new_page()
    pages = data.preprocess(doc.tobytes())
    assert [p["page"] for p in pages] == [1, 2]
    assert not pages[0]["needs_visual_or_ocr_review"]
    assert pages[1]["needs_visual_or_ocr_review"]
    with pytest.raises(ValueError):
        data.preprocess(b"bad")


def page(number, yes):
    return {"page": number, "scores": {key: {"yes": yes, "no": 1 - yes} for key in data.QUESTIONS},
            "characters": 100, "approx_tokens": 25, "classification_seconds": .123456789,
            "needs_visual_or_ocr_review": False, "text_extraction_warning": None}


def test_probabilities():
    data.validate_scores(page(1, .943218123456789)["scores"])
    for bad in [float('nan'), float('inf'), -1, 2]:
        with pytest.raises(ValueError):
            data.validate_scores(page(1, bad)["scores"])
    with pytest.raises(ValueError):
        data.validate_scores({})
    scores = page(1, .7)["scores"]
    scores["overall_relevance"]["no"] = .7
    with pytest.raises(ValueError):
        data.validate_scores(scores)


def test_threshold_and_expansion():
    pages = [page(1, .5), page(2, .6), page(3, .9), {"page": 4, "scores": None}]
    assert data.select(pages, .5) == [2, 3]
    assert data.expand([1, 3, 4], 4) == [1, 2, 3, 4]
    assert data.expand([1], 1) == [1]
    assert data.expand([], 4) == []
    assert data.thresholds(pages)["0.50"]["retained_percent"] == 50


def test_exports(tmp_path):
    precise = .943218123456789
    pages = [page(1, precise), page(2, .00000123456789)]
    pages.append({**page(3, .5), "scores": None, "classification_status": "unscored"})
    result = {"run": {}, "pages": pages}
    paths = data.export(result, tmp_path, "test")
    loaded = json.loads(open(paths["json"]).read())
    assert len(loaded["pages"]) == 3
    assert loaded["pages"][0]["scores"]["overall_relevance"]["yes"] == precise
    rows = list(csv.DictReader(open(paths["csv"])))
    assert len(rows) == 3
    assert float(rows[0]["overall_relevance_yes"]) == precise
    assert rows[-1]["overall_relevance_yes"] == ""
