"""Streamlit policy controls. Labels are session-only, outside persisted settings."""
import math
import streamlit as st
from app import settings as config


def install(value):
    st.session_state.policy_settings = config.validate(value)
    for key, item in value.items():
        st.session_state[f"policy_{key}"] = item


def initialize():
    if "policy_settings" not in st.session_state:
        value = config.load()
        install(value)
        st.session_state.policy_saved_settings = value


def edited():
    value = {key: st.session_state[f"policy_{key}"] for key in config.DEFAULTS}
    value["preset"] = "custom"
    st.session_state.policy_settings = config.validate(value)
    st.session_state.policy_preset = "custom"


def save():
    config.save(st.session_state.policy_settings)
    st.session_state.policy_saved_settings = dict(st.session_state.policy_settings)
    st.session_state.policy_notice = "Settings saved. They will persist across GUI restarts."


def reset():
    value = config.reset()
    install(value)
    st.session_state.policy_saved_settings = value
    st.session_state.policy_notice = "Defaults restored and saved."


def load_preset():
    install(config.preset(st.session_state.preset_to_load, st.session_state.policy_settings, config.load_presets()))
    st.session_state.policy_notice = "Preset loaded. Click Save Settings to make it the startup policy."


def save_preset():
    try:
        config.save_preset(st.session_state.new_preset_name.strip(), st.session_state.policy_settings)
        st.session_state.policy_notice = "Custom preset saved. Existing presets were not overwritten."
    except ValueError as exc:
        st.session_state.policy_notice = str(exc)


def render(run_key, total_pages):
    initialize()
    st.header("Settings")
    st.caption("All controls below operate after inference. Editing settings or labels never calls SemIf.")
    current = st.session_state.policy_settings
    st.write("Active preset:", config.PRESET_LABELS.get(current["preset"], current["preset"]))
    if current != st.session_state.policy_saved_settings:
        st.info("Unsaved policy changes are active for this session. Save Settings to persist them.")
    if st.session_state.get("policy_notice"):
        st.caption(st.session_state.policy_notice)
    st.subheader("1. Selection Strategy")
    st.selectbox("Selection mode", list(config.MODES), format_func=config.MODES.get, key="policy_mode", on_change=edited)
    st.caption("All policy thresholds use >=. Raw probabilities and A/B answer ordering remain unchanged.")
    st.subheader("2. Thresholds")
    for key, label in [
        ("requested_data_threshold", "Requested data threshold"),
        ("overall_relevance_threshold", "Overall relevance rescue threshold"),
        ("supporting_context_threshold", "Supporting context rescue threshold"),
        ("cross_reference_threshold", "Cross-reference rescue threshold"),
        ("secondary_min_overall", "Minimum overall for context / cross-reference rescue"),
        ("financial_table_threshold", "Financial table rescue threshold"),
        ("financial_table_min_overall", "Minimum overall for financial table rescue"),
    ]:
        st.number_input(label, min_value=0.0, max_value=1.0, step=.01, format="%.2f", key=f"policy_{key}", on_change=edited)
    st.checkbox("Enable financial-table rescue (Recall First OR only)", key="policy_financial_table_enabled", on_change=edited)
    st.caption("Context and cross-reference rescues require their high threshold AND the secondary overall gate. Financial tables are diagnostic by default.")
    st.subheader("3. Weighted Score")
    for field, key in config.WEIGHTS.items():
        st.number_input(f"{field} weight", min_value=0.0, step=.05, format="%.4f", key=f"policy_{key}", on_change=edited)
    st.number_input("Weighted score threshold", min_value=0.0, step=.01, key="policy_weighted_threshold", on_change=edited)
    total = config.weight_sum(st.session_state.policy_settings)
    st.write(f"Weight sum: {total:.6f}")
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        st.warning("Weights do not sum to 1.0. The weighted sum is used exactly as entered; no normalization is applied.")
    st.caption("Routing Score is always visible as a diagnostic. It changes selection only in Weighted Score mode and is not a probability.")
    st.subheader("4. Neighbor Expansion")
    st.selectbox("Neighbor Radius", [0, 1, 2], key="policy_neighbor_radius", on_change=edited)
    st.caption("Expansion starts from model-rule selections plus enabled manual-review inclusions. Neighbor-added pages are reported separately.")
    st.subheader("5. Safety / Manual Review")
    st.checkbox("Always include OCR/text review pages", key="policy_always_include_ocr_review", on_change=edited)
    st.checkbox("Always include router/unscored review pages", key="policy_always_include_router_review", on_change=edited)
    st.caption("Benchmark — Direct Fields starts with these inclusions off for a pure requested-data comparison. Production — Recall First turns both on. Review queues remain visible regardless.")
    st.subheader("6. Benchmark Evaluation")
    st.text_input("Known relevant pages", key=f"ground_truth_{run_key}", placeholder="12,20,26,32,40", disabled=not total_pages)
    st.caption("Evaluation only: labels never enter prompts, the objective, page text, or probabilities. All omitted pages are assumed negative. "
               "Commas, spaces and ranges (1-3) are accepted; blank means no evaluation, [] means explicitly no relevant pages. "
               "Labels are scoped to this run and are not written to the settings file.")
    st.subheader("7. Presets")
    saved = config.load_presets()
    choices = list(config.PRESET_LABELS) + ["saved:" + name for name in saved]
    st.selectbox("Preset to load", choices, format_func=lambda name: config.PRESET_LABELS.get(name, name.removeprefix("saved:")), key="preset_to_load")
    st.button("Load Preset", on_click=load_preset)
    st.text_input("New preset name (no document contents)", key="new_preset_name")
    st.button("Save as Preset", on_click=save_preset)
    st.button("Save Settings", type="primary", on_click=save)
    st.button("Reset to Defaults", on_click=reset)
    st.caption(f"Settings: {config.SETTINGS_PATH} · Custom presets: {config.PRESETS_PATH}")
    return st.session_state.policy_settings
