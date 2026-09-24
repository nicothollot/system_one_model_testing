"""Persist only selection-policy parameters, never labels or document contents."""
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile

CONFIG = Path(__file__).resolve().parents[1] / "config"
SETTINGS_PATH = CONFIG / "router_settings.json"
PRESETS_PATH = CONFIG / "router_presets.json"
DEFAULTS = json.loads((CONFIG / "router_defaults.json").read_text())
MODES = {"requested_data_only": "Requested Data Only", "recall_or": "Recall First OR", "weighted": "Weighted Score"}
PRESET_LABELS = {"benchmark_direct": "Benchmark — Direct Fields", "production_recall": "Production — Recall First", "custom": "Custom"}
WEIGHTS = {"requested_data": "requested_data_weight", "overall_relevance": "overall_relevance_weight",
           "supporting_context": "supporting_context_weight", "cross_reference_or_footnote": "cross_reference_weight",
           "financial_table": "financial_table_weight"}


def defaults():
    return copy.deepcopy(DEFAULTS)


def validate(settings):
    if set(settings) != set(DEFAULTS):
        raise ValueError("Settings must contain only the defined policy keys; ground truth and document data are not settings")
    if settings["schema_version"] != 1 or settings["mode"] not in MODES:
        raise ValueError("Unsupported settings version or selection mode")
    if not isinstance(settings["preset"], str) or not settings["preset"] or len(settings["preset"]) > 80:
        raise ValueError("Invalid preset identifier")
    for key, value in settings.items():
        if key in {"schema_version", "mode", "preset"}:
            continue
        if isinstance(DEFAULTS[key], bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
        elif key == "neighbor_radius":
            if type(value) is not int or value not in (0, 1, 2):
                raise ValueError("Neighbor radius must be 0, 1, or 2")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be finite and nonnegative")
        elif key not in WEIGHTS.values() and key != "weighted_threshold" and value > 1:
            raise ValueError(f"{key} must be between 0 and 1")
    return copy.deepcopy(settings)


def preset(name, current=None, custom_presets=None):
    if name == "custom":
        value = validate(current) if current is not None else defaults()
    elif name == "benchmark_direct":
        value = defaults()
    elif name == "production_recall":
        value = defaults()
        value.update(mode="recall_or", neighbor_radius=1, always_include_ocr_review=True, always_include_router_review=True)
    elif name.startswith("saved:") and name[6:] in (custom_presets or {}):
        value = validate(custom_presets[name[6:]])
    else:
        raise ValueError(f"Unknown preset: {name}")
    value["preset"] = name
    return value


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            name = handle.name
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def save(settings, path=None):
    atomic_json(path or SETTINGS_PATH, validate(settings))


def load(path=None):
    path = Path(path or SETTINGS_PATH)
    if not path.exists():
        save(defaults(), path)
    return validate(json.loads(path.read_text()))


def reset(path=None):
    value = defaults()
    save(value, path)
    return value


def load_presets(path=None):
    path = Path(path or PRESETS_PATH)
    values = json.loads(path.read_text()) if path.exists() else {}
    for name, value in values.items():
        validate(value)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}", name):
            raise ValueError("Invalid saved preset name")
    return values


def save_preset(name, settings, path=None, replace=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,63}", name):
        raise ValueError("Preset names must use 1–64 letters, digits, spaces, underscores or hyphens")
    path = Path(path or PRESETS_PATH)
    values = load_presets(path)
    if name in values and not replace:
        raise ValueError("That preset already exists; choose a new name")
    values[name] = validate(settings)
    atomic_json(path, values)


def weight_sum(settings):
    return sum(settings[key] for key in WEIGHTS.values())
