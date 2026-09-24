"""Inference inputs are isolated from post-inference policy and evaluation state."""
import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
from app import data, selection, settings_ui, criteria
from app.engine import ROOT, run
from app.runtime import resident_router as process_router

LABELS = {"overall_relevance": "Overall Relevance", "requested_data": "Requested Data", "supporting_context": "Supporting Context",
          "financial_table": "Financial Table", "cross_reference_or_footnote": "Cross Reference / Footnote", "routing_score": "Routing Score"}
st.set_page_config(page_title="Kairon page router benchmark", layout="wide")
st.title("Kairon Insights — PDF page router")
st.caption("Local SemIf probabilities on GX10. Selection policies and benchmark evaluation use saved probabilities only.")


@st.cache_resource
def resident_router():
    return process_router()


inputs_tab, results_tab, settings_tab = st.tabs(["Analyze / Saved Runs", "Results", "Settings"])
with inputs_tab:
    pdf = st.file_uploader("PDF", type=["pdf"])
    instructions = st.file_uploader("Instructions JSON", type=["json"])
    reference = st.file_uploader("Reference XLSX", type=["xlsx"])
    if st.button("Analyze Pages", type="primary", disabled=not all([pdf, instructions, reference])):
        st.session_state.pop("result", None)
        with st.status("Starting analysis", expanded=True) as status:
            label = st.empty()
            try:
                # Only the original three inputs; no selection settings or evaluation labels.
                result = run(resident_router(), pdf.name, pdf.getvalue(), instructions.getvalue(), reference.getvalue(),
                             progress=label.write, input_names={"pdf": pdf.name, "json": instructions.name, "xlsx": reference.name})
                st.session_state.result = result
                success = result["run"]["status"] == "COMPLETED"
                status.update(label="Analysis exported" if success else result["run"]["status"], state="complete" if success else "error")
            except Exception as exc:
                status.update(label="Analysis failed", state="error")
                st.error(str(exc))
    saved = sorted(list((ROOT / "outputs").glob("page_router_run_*.json")) + list((ROOT / "outputs").glob("page_router_selection_*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
    if saved:
        previous = st.selectbox("Saved run or selection snapshot", saved, format_func=lambda p: p.name, key="saved_run")
        if st.button("Open Saved Run"):
            try:
                raw = selection.model_result(json.loads(previous.read_text(encoding="utf-8")))
                selection.universe(raw["pages"])
                st.session_state.result = raw
                st.success("Saved probabilities loaded. Your active settings were preserved. Open Results or Settings.")
            except (ValueError, KeyError, OSError) as exc:
                st.error(f"Cannot open saved run: {exc}")
    st.caption("Inference exports are immutable. Export Selection Snapshot in Results saves a separate policy/evaluation snapshot.")

raw = selection.model_result(st.session_state.result) if "result" in st.session_state else None
run_key = selection.digest(raw)[:16] if raw else "no_run"
with settings_tab:
    with st.expander("Current classifier criteria / exact prompts — new inference only"):
        st.json(criteria.versions({"prompt_version": criteria.PROMPT_VERSION, "classifier_criteria_version": criteria.CRITERIA_VERSION}))
        st.caption("Changing classifier wording requires new inference. Selection thresholds use saved probabilities only. v1 and v2 probabilities are not directly interchangeable.")
        for key, question in criteria.QUESTIONS.items():
            st.write(key)
            st.code(question, language=None)
            st.json(criteria.OPTIONS[key])
    try:
        active_settings = settings_ui.render(run_key, len(raw["pages"]) if raw else 0)
    except (ValueError, OSError) as exc:
        st.error(f"Settings file error: {exc}")
        if st.button("Reset invalid settings file"):
            settings_ui.reset()
            st.rerun()
        st.stop()

with results_tab:
    if raw is None:
        st.info("Analyze the three input files or open a saved run, then adjust Settings without rerunning the model.")
    else:
        metrics, pages = raw["run"], raw["pages"]
        truth = None
        try:
            truth = selection.parse_ground_truth(st.session_state.get(f"ground_truth_{run_key}", ""), len(pages))
        except ValueError as exc:
            st.error(str(exc))
        policy = selection.select_pages(pages, active_settings, truth)
        st.session_state.current_selection = policy
        scored, complete = len(pages) - len(policy["unscored_pages"]), policy["statistics_valid"]
        st.subheader("Run overview")
        st.write("Saved classifier versions:", criteria.versions(metrics))
        st.caption("Legacy v1 and semantic-equivalence v2 probabilities are not directly interchangeable. Settings only reselect saved probabilities.")
        st.write(f"**{metrics['pdf']}** · {len(pages)} pages · {metrics['model']} · {metrics['backend']} · {metrics['device']}")
        st.write(f"**{scored} / {len(pages)} successfully scored**")
        if not complete:
            failure = "FAILED_INPUT_PREPARATION" if metrics["status"] == "FAILED_INPUT_PREPARATION" else "FAILED_CLASSIFICATION" if not scored else "PARTIAL_CLASSIFICATION"
            st.error(f"{failure}: zero selected pages DOES NOT mean zero relevant pages. Unscored pages are unknown. "
                     "Only a policy preview/manual-review queue is available; reduction, benchmark metrics and sweeps are disabled.")
            st.write("Unscored pages:", policy["unscored_pages"])
            if metrics.get("classification_error"):
                st.error(metrics["classification_error"])
        with st.expander("Original inference timings, memory, and provenance"):
            st.json(metrics)
        with st.expander("Compiled routing objective — exact text sent to SemIf"):
            st.code(raw["inputs"].get("compiled_routing_objective", raw["inputs"].get("constructed_extraction_objective", "Unavailable")), language=None)
            st.json(raw["inputs"].get("routing_objective_compilation", {"version": "legacy objective"}))
        with st.expander("Complete original inputs — immutable debugging data"):
            st.json({key: raw["inputs"].get(key) for key in ("instructions_json", "parsed_reference_fields", "filenames", "sha256")})
        st.subheader("Active page selection")
        st.write(f"Preset: **{policy['preset']}** · Mode: **{policy['mode']}** · Neighbor radius: **{active_settings['neighbor_radius']}**")
        for label, key in [("Model-rule selected pages", "model_selected_pages"), ("Manual-review inclusions", "manual_review_selected_pages"),
                           ("Raw selected pages (before neighbors)", "raw_selected_pages"), ("Neighbor-added pages", "neighbor_added_pages"),
                           ("Neighbor-expanded pages", "expanded_selected_pages"), ("Final pages", "final_selected_pages")]:
            st.write(label + ":", policy[key])
        if complete:
            st.write({"raw_selected_count": len(policy["raw_selected_pages"]), "expanded_selected_count": len(policy["expanded_selected_pages"]),
                      "final_selected_count": len(policy["final_selected_pages"]), "rejected_count": len(pages) - len(policy["final_selected_pages"]),
                      "page_reduction_percent": policy["page_reduction_percent"]})
        st.write("PDF/text quality review queue:", policy["ocr_review_pages"])
        st.write("Router/classification review queue:", policy["router_review_pages"])
        table = pd.DataFrame(data.csv_rows(pages))
        table["selected"] = table.page.isin(policy["final_selected_pages"])
        table["selection_reason"] = table.page.map(lambda n: " | ".join(policy["selection_reasons"].get(str(n), [])))
        table["routing_score"] = table.page.map(lambda n: policy["routing_scores"][str(n)])
        leading = ["page", "selected", "selection_reason", "routing_score"] + [f"{key}_yes" for key in LABELS if key != "routing_score"]
        table = table[leading + [key for key in table.columns if key not in leading]]
        st.subheader("Page results — raw probabilities remain visible")
        sort = st.selectbox("Sort results", ["requested_data_yes", "routing_score", "overall_relevance_yes", "supporting_context_yes",
                                             "financial_table_yes", "cross_reference_or_footnote_yes", "selected", "page"], key="result_sort")
        descending = st.checkbox("Descending sort", value=True, key="result_sort_descending")
        ordered = table.sort_values(sort, ascending=not descending, na_position="last")
        columns = {f"{key}_{option}": st.column_config.NumberColumn(f"{label} ({option})", format="%.6f")
                   for key, label in LABELS.items() if key != "routing_score" for option in ("yes", "no")}
        columns.update(selected=st.column_config.CheckboxColumn("Selected"), selection_reason="Selection Reason",
                       routing_score=st.column_config.NumberColumn("Routing Score", format="%.6f"))
        styled = ordered.style.apply(lambda row: ["background-color: #dcefdc; color: #153e1b" if row["selected"] else "" for _ in row], axis=1)
        event = st.dataframe(styled, hide_index=True, column_config=columns, on_select="rerun", selection_mode="single-row", key=f"pages_{run_key}")
        st.subheader("Document graph")
        chosen = st.multiselect("Graph series", list(LABELS), default=["requested_data", "overall_relevance"], format_func=LABELS.get, key="graph_series")
        if chosen and scored:
            graph = pd.DataFrame({"page": table.page, **{key: table["routing_score" if key == "routing_score" else key + "_yes"] for key in chosen}})
            melted = graph.melt("page", var_name="Series", value_name="Value")
            chart = alt.Chart(melted).mark_line(point=True).encode(x=alt.X("page:Q", title="PDF page number"), y=alt.Y("Value:Q", title="Probability / routing score"), color="Series:N", tooltip=["page:Q", "Series:N", "Value:Q"])
            rules = []
            if active_settings["mode"] in ("requested_data_only", "recall_or") and "requested_data" in chosen:
                rules.append({"Series": "requested_data threshold", "Value": active_settings["requested_data_threshold"]})
            if active_settings["mode"] == "recall_or" and "overall_relevance" in chosen:
                rules.append({"Series": "overall_relevance rescue threshold", "Value": active_settings["overall_relevance_threshold"]})
            if active_settings["mode"] == "weighted" and "routing_score" in chosen:
                rules.append({"Series": "weighted threshold", "Value": active_settings["weighted_threshold"]})
            if rules:
                chart += alt.Chart(pd.DataFrame(rules)).mark_rule(strokeDash=[6, 4]).encode(y="Value:Q", color="Series:N", tooltip=["Series:N", "Value:Q"])
            st.altair_chart(chart, width="stretch")
            st.caption("Dashed lines show active standalone thresholds. Context/cross-reference/financial rescues also require their overall gate (see Settings).")
        st.subheader("Benchmark evaluation — final selected pages")
        if truth is None:
            st.info("Enter known relevant pages in Settings → Benchmark Evaluation. Labels are used only for post-inference evaluation.")
        elif complete:
            evaluation = policy["benchmark_metrics"]
            st.metric("FALSE NEGATIVE PAGES", evaluation["false_negatives"])
            st.write("FALSE NEGATIVE PAGES:", evaluation["false_negative_pages"])
            st.write("FALSE POSITIVE PAGES:", evaluation["false_positive_pages"])
            st.caption("These metrics assume your supplied relevant-page list is exhaustive. Undefined ratios are displayed as undefined.")
            st.dataframe(pd.DataFrame([{"Metric": key, "Value": "undefined" if value is None else str(value)} for key, value in evaluation.items() if not isinstance(value, list)]), hide_index=True)
            st.subheader("Threshold sweep / calibration — no model calls")
            sweep_series = st.selectbox("Sweep series", selection.SERIES, format_func=LABELS.get, key="sweep_series")
            sweep = selection.threshold_sweep(pages, truth, sweep_series, active_settings)
            st.caption(sweep["scope"])
            st.write({"highest_threshold_achieving_100_percent_recall": sweep["highest_threshold_full_recall"],
                      "highest_F2_threshold": sweep["highest_f2_threshold"], "highest_F1_threshold": sweep["highest_f1_threshold"]})
            st.caption("Diagnostics only: your active threshold is never changed. Weighted sums may exceed the 0–1 sweep grid if weights do not sum to one.")
            frame = pd.DataFrame(sweep["rows"])
            st.line_chart(frame.set_index("threshold")[["precision", "recall", "f1", "f2"]])
            st.dataframe(frame[["threshold", "selected_pages", "page_reduction_percent", "precision", "recall", "f1", "f2", "false_positives", "false_negatives"]], hide_index=True)
        st.subheader("Page detail")
        selected_rows = event.selection.rows
        default_page = int(ordered.iloc[selected_rows[0]]["page"]) if selected_rows and selected_rows[0] < len(ordered) else 1
        number = st.number_input("Page number", min_value=1, max_value=len(pages), value=default_page, key=f"detail_{run_key}_{default_page}")
        page = next(p for p in pages if p["page"] == number)
        st.write("Selection reasons:", policy["selection_reasons"].get(str(number), []))
        st.text_area("Full extracted page text", page["extracted_text"], height=250)
        st.code(page.get("classifier_input", "Page was not scored"), language=None)
        for index, key in enumerate(data.QUESTIONS):
            with st.expander(f"Criterion: {key}"):
                st.write(criteria.versions(page if "prompt_version" in page else metrics))
                st.code(page.get("classification_questions", {}).get(key, "Unavailable in this saved run"), language=None)
                options = page.get("classification_options", [])
                st.json(options.get(key, []) if isinstance(options, dict) else options)
                probabilities = (page.get("scores") or {}).get(key, {})
                st.json(probabilities)
                if probabilities:
                    st.write("Decision margin (YES − NO):", probabilities["yes"] - probabilities["no"])
                distributions = page.get("raw_distributions") or []
                st.json(distributions[index] if index < len(distributions) else {})
                st.caption("Raw distribution prompt_version identifies the unchanged upstream SemIf renderer; application criteria versions are shown above.")
                st.write("Exact prompt tokens:", page.get("exact_prompt_tokens", {}).get(key))
                st.code(page.get("exact_prompts", {}).get(key, "Unavailable in this saved run"), language=None)
        st.json(page)
        st.subheader("Exports")
        if st.button("Export Selection Snapshot", key="export_selection"):
            paths = selection.export_selection(raw, policy, ROOT / "outputs")
            st.session_state.policy_export = {"policy": policy, "run_key": run_key, "paths": paths}
        exported = st.session_state.get("policy_export")
        if exported and exported["run_key"] == run_key and exported["policy"] == policy:
            for suffix, path in exported["paths"].items():
                st.download_button(f"Download selection {suffix.upper()}", Path(path).read_bytes(), file_name=Path(path).name)
            st.write("Selection snapshot files:", exported["paths"])
        else:
            st.caption("Export a new snapshot to capture current settings, reasons, final pages and benchmark labels/metrics. Raw inference files are never overwritten.")
        with st.expander("Immutable raw inference exports"):
            for suffix, path in metrics.get("exports", {}).items():
                if Path(path).exists():
                    st.download_button(f"Download raw {suffix.upper()}", Path(path).read_bytes(), file_name=Path(path).name)
            st.write(metrics.get("exports", {}))
            st.caption(f"Original run log: {metrics.get('log')}")
