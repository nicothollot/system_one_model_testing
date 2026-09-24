"""Pure post-inference policy/evaluation functions; never import an inference backend."""
import copy
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import uuid

from app import data
from app import settings as config

VERSION = "page-selection-v1"
SERIES = ["requested_data", "overall_relevance", "supporting_context", "cross_reference_or_footnote", "financial_table", "routing_score"]


def model_result(result):
    # Accept both original run JSON and an exported policy snapshot without adopting its policy.
    raw = result.get("model_result", result)
    return {key: value for key, value in raw.items() if key != "selection"}


def digest(result):
    return hashlib.sha256(json.dumps(model_result(result), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def universe(pages):
    numbers = [p["page"] for p in pages]
    if not numbers or any(type(n) is not int for n in numbers) or sorted(numbers) != list(range(1, len(pages) + 1)):
        raise ValueError("A saved run must contain exactly one entry for every page numbered 1 through N")
    return set(numbers)


def valid_scores(page):
    try:
        data.validate_scores(page.get("scores") or {})
        return True
    except (ValueError, TypeError, KeyError):
        return False


def review_flags(page):
    # Old exports sometimes set OCR=True for model errors despite text status='ok'.
    status = page.get("text_extraction_status")
    ocr = status in ("sparse", "error") if status in ("ok", "sparse", "error") else bool(page.get("needs_visual_or_ocr_review"))
    return ocr, bool(page.get("needs_router_review")) or not valid_scores(page)


def routing_score(page, settings):
    if not valid_scores(page):
        return None
    return sum(page["scores"][field]["yes"] * settings[weight] for field, weight in config.WEIGHTS.items())


def parse_ground_truth(value, total_pages):
    value = value.strip()
    if not value:
        return None
    if value.casefold() in ("none", "[]"):
        return []
    selected = set()
    for part in re.split(r"[,\s]+", re.sub(r"\s*-\s*", "-", value)):
        if not re.fullmatch(r"\d+(?:-\d+)?", part):
            raise ValueError(f"Invalid ground-truth page entry: {part!r}")
        bounds = [int(v) for v in part.split("-")]
        first, last = bounds[0], bounds[-1]
        if not 1 <= first <= last <= total_pages:
            raise ValueError(f"Ground-truth pages must be within 1–{total_pages}, with ascending ranges")
        selected.update(range(first, last + 1))
    return sorted(selected)


def benchmark_metrics(selected, truth, total_pages):
    all_pages = set(range(1, total_pages + 1))
    selected, truth = set(selected), set(truth)
    if not selected <= all_pages or not truth <= all_pages:
        raise ValueError("Evaluation page numbers are outside the document")
    tp, fp, fn, tn = selected & truth, selected - truth, truth - selected, all_pages - (selected | truth)
    a, b, c, d = len(tp), len(fp), len(fn), len(tn)
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    return {"true_positives": a, "false_positives": b, "true_negatives": d, "false_negatives": c,
            "precision": ratio(a, a + b), "recall": ratio(a, a + c), "specificity": ratio(d, d + b),
            "f1": ratio(2 * a, 2 * a + b + c), "f2": ratio(5 * a, 5 * a + b + 4 * c),
            "false_negative_rate": ratio(c, a + c), "false_positive_rate": ratio(b, b + d),
            "total_pages": total_pages, "selected_pages": len(selected), "page_reduction_percent": 100 * (1 - len(selected) / total_pages),
            "true_positive_pages": sorted(tp), "false_positive_pages": sorted(fp), "true_negative_pages": sorted(tn), "false_negative_pages": sorted(fn)}


def select_pages(pages, settings, ground_truth=None):
    settings = config.validate(settings)
    all_pages = universe(pages)
    reasons = {n: [] for n in sorted(all_pages)}
    model_selected, manual_selected, ocr_queue, router_queue, unscored = set(), set(), [], [], []
    scores = {}
    for page in pages:
        n = page["page"]
        scores[n] = routing_score(page, settings)
        if valid_scores(page):
            p = {key: value["yes"] for key, value in page["scores"].items()}
            mode = settings["mode"]
            if mode in ("requested_data_only", "recall_or") and p["requested_data"] >= settings["requested_data_threshold"]:
                reasons[n].append("requested_data_threshold")
            if mode == "recall_or":
                if p["overall_relevance"] >= settings["overall_relevance_threshold"]:
                    reasons[n].append("overall_relevance_threshold")
                if p["overall_relevance"] >= settings["secondary_min_overall"]:
                    if p["supporting_context"] >= settings["supporting_context_threshold"]:
                        reasons[n].append("supporting_context_rescue")
                    if p["cross_reference_or_footnote"] >= settings["cross_reference_threshold"]:
                        reasons[n].append("cross_reference_rescue")
                if settings["financial_table_enabled"] and p["financial_table"] >= settings["financial_table_threshold"] and p["overall_relevance"] >= settings["financial_table_min_overall"]:
                    reasons[n].append("financial_table_rescue")
            if mode == "weighted" and scores[n] >= settings["weighted_threshold"]:
                reasons[n].append("weighted_score")
            if reasons[n]:
                model_selected.add(n)
        else:
            unscored.append(n)
        ocr, router = review_flags(page)
        if ocr:
            ocr_queue.append(n)
        if router:
            router_queue.append(n)
        for flag, enabled, reason in ((ocr, settings["always_include_ocr_review"], "ocr_review"),
                                      (router, settings["always_include_router_review"], "router_review")):
            if flag and enabled:
                manual_selected.add(n)
                reasons[n].append(reason)
    raw = model_selected | manual_selected
    expanded = set(raw)
    for seed in sorted(raw):
        for n in range(seed - settings["neighbor_radius"], seed + settings["neighbor_radius"] + 1):
            if n in all_pages and n != seed:
                expanded.add(n)
                reasons[n].append(f"neighbor_of_page_{seed}")
    complete = not unscored
    evaluation = benchmark_metrics(expanded, ground_truth, len(pages)) if ground_truth is not None and complete else None
    return {"version": VERSION, "preset": settings["preset"], "mode": settings["mode"], "settings": settings,
            "comparison": ">= (inclusive)", "model_selected_pages": sorted(model_selected), "manual_review_selected_pages": sorted(manual_selected),
            "raw_selected_pages": sorted(raw), "expanded_selected_pages": sorted(expanded), "neighbor_added_pages": sorted(expanded - raw),
            "final_selected_pages": sorted(expanded), "selection_reasons": {str(n): values for n, values in reasons.items() if values},
            "routing_scores": {str(n): value for n, value in scores.items()}, "unscored_pages": sorted(unscored),
            "ocr_review_pages": sorted(ocr_queue), "router_review_pages": sorted(router_queue), "statistics_valid": complete,
            "page_reduction_percent": 100 * (1 - len(expanded) / len(pages)) if complete else None,
            "benchmark_ground_truth": copy.deepcopy(ground_truth), "benchmark_metrics": evaluation,
            "benchmark_scope": "Final pages, including manual-review rules and neighbors; omitted ground-truth pages are treated as negative",
            "weighted_score_note": "Raw weighted sum, never normalized; not a calibrated probability",
            "weight_sum": config.weight_sum(settings)}


def threshold_sweep(pages, truth, series="requested_data", settings=None):
    universe(pages)
    if truth is None or any(not valid_scores(p) for p in pages):
        raise ValueError("A sweep requires supplied ground truth and valid scores for every page")
    if series not in SERIES:
        raise ValueError("Unknown sweep series")
    settings = config.validate(settings or config.defaults())
    values = {p["page"]: routing_score(p, settings) if series == "routing_score" else p["scores"][series]["yes"] for p in pages}
    rows = []
    for step in range(101):
        threshold = step / 100
        chosen = [n for n, value in values.items() if value >= threshold]
        rows.append({"threshold": threshold, **benchmark_metrics(chosen, truth, len(pages))})
    def best(key):
        eligible = [row for row in rows if row[key] is not None]
        return max(eligible, key=lambda row: (row[key], row["threshold"]))["threshold"] if eligible else None
    return {"series": series, "scope": "Single-signal >= threshold only; no rescue, manual-review, or neighbor rules. Grid 0.00–1.00; ties favor higher threshold.",
            "rows": rows, "highest_threshold_full_recall": max((r["threshold"] for r in rows if r["recall"] == 1), default=None),
            "highest_f1_threshold": best("f1"), "highest_f2_threshold": best("f2")}


def export_selection(result, selection, folder):
    """Write a new snapshot; never overwrite or mutate the raw inference export."""
    raw = model_result(result)
    source_hash = digest(raw)
    snapshot = copy.deepcopy(raw)
    snapshot["selection"] = copy.deepcopy(selection)
    now = dt.datetime.now(dt.timezone.utc)
    snapshot["selection"].update(exported_at=now.isoformat(), source_model_result_sha256=source_hash)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = "page_router_selection_" + now.strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:6]
    paths = {suffix: folder / f"{stem}.{suffix}" for suffix in ("json", "csv")}
    with paths["json"].open("x", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, ensure_ascii=False, allow_nan=False)
    rows = data.csv_rows(raw["pages"])
    for row in rows:
        n = row["page"]
        row.update(selected=n in selection["final_selected_pages"], model_selected=n in selection["model_selected_pages"],
                   raw_selected=n in selection["raw_selected_pages"], neighbor_added=n in selection["neighbor_added_pages"],
                   routing_score=selection["routing_scores"][str(n)], selection_reasons=" | ".join(selection["selection_reasons"].get(str(n), [])))
    with paths["csv"].open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {key: str(value) for key, value in paths.items()}
