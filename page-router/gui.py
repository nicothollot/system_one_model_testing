"""Start with Streamlit from the GX10 application directory."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from app import data
from app.engine import ROOT, Router, run

st.set_page_config(page_title="Kairon page router benchmark", layout="wide")
st.title("Kairon Insights — PDF page router")
st.caption("Local SemIf option probabilities on GX10. Page selection only. Scores are uncalibrated; inspect false negatives before choosing a threshold.")


@st.cache_resource
def resident_router():
    return Router()


pdf = st.file_uploader("PDF", type=["pdf"])
instructions = st.file_uploader("Instructions JSON", type=["json"])
reference = st.file_uploader("Reference XLSX", type=["xlsx"])
if st.button("Analyze Pages", type="primary", disabled=not all([pdf, instructions, reference])):
    st.session_state.pop("result", None)
    with st.status("Starting analysis", expanded=True) as status:
        label = st.empty()
        try:
            result = run(resident_router(), pdf.name, pdf.getvalue(), instructions.getvalue(), reference.getvalue(),
                         progress=label.write, input_names={"pdf": pdf.name, "json": instructions.name, "xlsx": reference.name})
            st.session_state.result = result
            successful = result["run"]["status"] == "COMPLETED"
            status.update(label="Analysis exported" if successful else result["run"]["status"], state="complete" if successful else "error")
        except Exception as exc:
            status.update(label="Analysis failed", state="error")
            st.error(str(exc))

saved = sorted((ROOT / "outputs").glob("page_router_run_*.json"), reverse=True)
if saved:
    with st.expander("Inspect a saved run without loading the model"):
        previous = st.selectbox("Saved run", saved, format_func=lambda path: path.name)
        if st.button("Open saved run"):
            st.session_state.result = json.loads(previous.read_text(encoding="utf-8"))

if "result" in st.session_state:
    result = st.session_state.result
    metrics, pages = result["run"], result["pages"]
    st.subheader("Run overview")
    st.write(f"**{metrics['pdf']}** · {metrics['total_pages']} pages · {metrics['model']} · {metrics['backend']} · {metrics['device']}")
    scored = sum(bool(p.get("scores")) for p in pages)
    complete = scored == len(pages)
    st.write(f"**{scored} / {len(pages)} successfully scored**")
    if not complete:
        failure = "FAILED_INPUT_PREPARATION" if metrics["status"] == "FAILED_INPUT_PREPARATION" else "FAILED_CLASSIFICATION" if not scored else "PARTIAL_CLASSIFICATION"
        st.error(f"{failure}: zero selected pages DOES NOT mean zero relevant pages. "
                 "Unscored pages are unknown. Threshold and reduction statistics are disabled for this run.")
        if metrics.get("classification_error"):
            st.error(metrics["classification_error"])
        st.write("Unscored pages:", [p["page"] for p in pages if not p.get("scores")])
    display_keys = ["model_revision", "semif_commit", "semif_version", "hostname", "device_name", "model_reused",
                    "model_load_seconds", "model_load_seconds_this_run", "input_parsing_seconds", "preprocessing_seconds",
                    "context_preparation_seconds", "model_forward_seconds", "classification_seconds", "export_seconds", "total_seconds",
                    "average_page_seconds", "median_page_seconds", "fastest_page", "slowest_page", "approx_total_page_tokens",
                    "exact_total_page_tokens", "shared_prefix_tokens_processed", "suffix_tokens_processed", "vllm_processes_unchanged",
                    "routing_objective_tokens", "exact_prompt_tokens_min", "exact_prompt_tokens_max", "available_token_headroom_min"]
    st.dataframe(pd.DataFrame([{"metric": key, "value": str(metrics.get(key))} for key in display_keys]), hide_index=True)
    with st.expander("Memory snapshots and runtime metadata"):
        st.json(metrics)
    if complete:
        st.dataframe(pd.DataFrame([{"overall relevance >": key, **value} for key, value in result["threshold_summary"].items()]), hide_index=True)
    with st.expander("Compiled routing objective — exact text sent to SemIf"):
        st.code(result["inputs"].get("compiled_routing_objective", result["inputs"].get("constructed_extraction_objective", "Unavailable")), language=None)
        st.json(result["inputs"].get("routing_objective_compilation", {"version": "legacy uncompiled objective"}))
    with st.expander("Complete original inputs — retained for debugging, not appended to classifier state"):
        st.json({key: result["inputs"].get(key) for key in ("instructions_json", "parsed_reference_fields", "filenames", "sha256")})

    table = pd.DataFrame(data.csv_rows(pages))
    st.subheader("Page results")
    sort_key = st.selectbox("Sort probability", [f"{key}_yes" for key in data.QUESTIONS])
    sorted_table = table.sort_values(sort_key, ascending=False, na_position="last")
    columns = {f"{key}_{option}": st.column_config.NumberColumn(format="%.6f") for key in data.QUESTIONS for option in ("yes", "no")}
    selection = st.dataframe(sorted_table, hide_index=True, column_config=columns, on_select="rerun", selection_mode="single-row", key="page_table")
    st.caption("Click a column header to sort, or select a row for its details. Exports retain full floating-point precision.")
    if scored:
        st.line_chart(table.set_index("page")[["overall_relevance_yes"]], x_label="PDF page number", y_label="Overall relevance probability")

    st.subheader("Selection simulator — no model rerun")
    if complete:
        threshold = st.slider("Selection Threshold (strictly greater than)", 0.0, 1.0, 0.5, 0.01)
        neighbors = st.toggle("Include ±1 Neighboring Page")
        selected = data.select(pages, threshold)
        expanded = data.expand(selected, len(pages)) if neighbors else selected
        st.write({"threshold": threshold, "raw_selected_count": len(selected), "expanded_selected_count": len(expanded),
                  "rejected_count": len(pages) - len(expanded), "raw_reduction_percent": 100 * (1 - len(selected) / len(pages)),
                  "final_reduction_percent": 100 * (1 - len(expanded) / len(pages))})
        st.write("Raw selected pages:", selected)
        st.write("Final pages:", expanded)
    st.write("PDF/text quality review queue:", [p["page"] for p in pages if p["needs_visual_or_ocr_review"]])
    st.write("Router/classification review queue:", [p["page"] for p in pages if p.get("needs_router_review") or not p.get("scores")])

    st.subheader("Page detail")
    selected_rows = selection.selection.rows
    default_page = int(sorted_table.iloc[selected_rows[0]]["page"]) if selected_rows else 1
    number = st.number_input("Page number", min_value=1, max_value=len(pages), value=default_page, key=f"detail_{default_page}")
    page = pages[number - 1]
    st.text_area("Full extracted page text", page["extracted_text"], height=250)
    st.code(page.get("classifier_input", "Page was not scored"), language=None)
    st.json(page)
    st.subheader("Exports")
    for suffix, path in metrics["exports"].items():
        st.download_button(f"Download {suffix.upper()}", Path(path).read_bytes(), file_name=Path(path).name,
                           mime="application/json" if suffix == "json" else "text/csv")
    st.caption(f"GX10 exports: {metrics['exports']} · Log: {metrics['log']}")
