# Post-inference selection settings and benchmark evaluation

The inference architecture is unchanged (criteria wording is versioned separately): Qwen3.5-4B, SemIf's direct shared scoring, A/B order, compact objective compiler and 8,192-token cap all remain as before. `app/selection.py` imports no inference backend and never changes probabilities. `app/settings.py` stores only policy parameters. Ground truth is evaluation input, not extraction input.

## Using the GUI

Run `./run.sh` from the repository root in NicoPC WSL and open `http://localhost:8507`. The tabs are **Analyze / Saved Runs**, **Results**, and **Settings**.

1. In Analyze / Saved Runs, choose an existing completed JSON and click **Open Saved Run**, or perform a new analysis with the original three inputs.
2. Open Settings. Changes recompute selection immediately from stored scores; there is no Apply button or inference call.
3. Under **7. Presets**, choose a preset and explicitly click **Load Preset**. Merely choosing an item does not overwrite your current policy. Choosing Custom preserves all existing values. Any policy edit marks the active policy Custom.
4. Click **Save Settings** to persist changes across sessions/restarts. **Reset to Defaults** explicitly restores and saves the benchmark defaults. **Save as Preset** creates a named reusable policy; existing named presets cannot be overwritten by this button.
5. Inspect Results for selected rows (highlighted), reasons, raw probabilities, weighted routing scores, page details, and the configurable graph.

Settings are stored on GX10 at `/home/kairon/kairon-page-router/config/router_settings.json`; named presets are in `config/router_presets.json`. These files are gitignored and excluded from source synchronization, so deployment does not overwrite custom settings. Versioned initial defaults are in `config/router_defaults.json`. The active settings file is created on first use. Settings files contain no document text, credentials, benchmark labels or run data.

Changes are session-local until Save Settings. Saved settings are shared by new GUI sessions on this GX10 installation; an already open session retains its current working policy. Opening another saved run preserves the active policy. Loading a selection snapshot uses its original model results with your current policy; it does not silently restore the snapshot's settings or labels. Its saved policy and labels remain available in the JSON for inspection/reuse.

## Strategies and presets

All new policy comparisons are **inclusive `>=`**. Legacy raw inference exports may contain a historical strict-`>` overall threshold summary; it remains untouched as historical data and is not used by the new selection UI.

**Benchmark — Direct Fields** (startup default): `requested_data >= 0.70`, radius 0. OCR/router automatic inclusions start off so this is a pure direct-signal benchmark. Both review queues remain visible, and incomplete inference still disables performance/reduction claims.

**Production — Recall First**: include requested_data >= 0.70 OR overall_relevance >= 0.95 OR supporting_context >= 0.95 with overall >= 0.70 OR cross_reference_or_footnote >= 0.97 with overall >= 0.70. OCR and router-review inclusion are on; neighbor radius is 1. Financial-table rescue is off. When enabled, it requires financial_table >= 0.98 AND overall >= 0.75 and applies only to Recall First OR mode. This preset name does not imply production integration or empirically established thresholds.

**Weighted Score**: `0.65*requested_data + 0.20*overall_relevance + 0.10*supporting_context + 0.05*cross_reference_or_footnote + 0.00*financial_table`, with threshold 0.55. Every weight and the threshold are editable. The application warns if the weights do not sum to one and uses the values exactly as entered. Routing Score is a diagnostic weighted sum, not a calibrated probability; it is shown in every mode but affects model-rule selection only in Weighted Score mode.

Safety inclusion toggles apply to any mode when enabled. Unscored/invalid-score pages enter the router-review queue even in legacy results without a `needs_router_review` field. For legacy OCR flags incorrectly set by classifier errors, preserved `text_extraction_status` takes precedence when available. This interpretation does not mutate old files.

## Reasons and neighbor stages

Results and exports distinguish:

- `model_selected_pages`: pages satisfying the active probability rule.
- `manual_review_selected_pages`: enabled OCR/router review inclusions.
- `raw_selected_pages`: union of model-rule and manual-review inclusions, before neighbors.
- `neighbor_added_pages`: new pages added by radius 0/1/2 expansion.
- `expanded_selected_pages` and `final_selected_pages`: the final union (no later filtering).

Neighbors expand from every raw selected page, including manual-review inclusions, and stay within document boundaries. Every applicable reason is preserved. A page already selected by a model rule can also receive `ocr_review`, `router_review`, or `neighbor_of_page_N` reasons. The neighbor-added list excludes pages already selected before expansion.

Failed/partial inference retains a prominent warning. Selection lists are only a policy/manual-review preview in that case: document reduction statistics, benchmark metrics and calibration sweeps are disabled. Zero selected pages does not mean zero relevant pages.

## Ground truth and metrics

In **Settings → 6. Benchmark Evaluation**, enter known relevant pages, for example `12,20,26,32,40`. Spaces, duplicates and ascending ranges such as `1-3, 8` are supported. Page numbers are validated against the current document. Blank disables evaluation; `[]` explicitly declares no relevant pages.

Labels are scoped to the current run in browser-session state and are never saved to global settings or passed to the router. They are included only in an explicitly exported selection snapshot. All omitted pages are assumed negative, so use an exhaustive annotation when interpreting measured precision/recall. The label list does not alter which pages are selected.

Results prominently shows **FALSE NEGATIVE PAGES** and **FALSE POSITIVE PAGES**, with exact page numbers. The metrics evaluate final selected pages including enabled review rules and neighbors: TP, FP, TN, FN, precision, recall, specificity, F1, F2, FNR, FPR, total/selected pages, and reduction. F2 uses `(5*TP)/(5*TP + 4*FN + FP)`, emphasizing recall. Zero-denominator ratios are `null` in JSON and displayed as undefined, not fabricated zeros.

## Calibration

When all pages are scored and ground truth is supplied, Results automatically sweeps requested_data from 0.00 through 1.00 at 0.01 increments. Other raw series and Routing Score are selectable. Each sweep is a **standalone single-signal rule** without OR rescues, manual-review inclusions or neighbors, regardless of the active policy. Its chart/table shows count, reduction, precision, recall, F1/F2 and FP/FN.

Diagnostics report the highest grid threshold retaining 100% recall and thresholds with highest F1/F2. Ties favor the higher threshold. These never change current settings. A weighted score outside [0,1] is possible with non-unit weights; its sweep still uses the explicitly displayed 0–1 grid.

The rationale for the defaults is the earlier 40-page observation: requested_data more consistently identified direct targets than overall_relevance. Requested data is therefore primary, overall relevance is a rescue signal, context and cross-references use high thresholds plus an overall gate, and financial_table stays diagnostic by default. Proper positive and negative annotations are still needed for threshold calibration.

## Exports and validation

New inference automatically writes raw JSON/CSV; policy evaluation leaves these original files unchanged. **Results → Export Selection Snapshot** writes new `outputs/page_router_selection_<UTC>_<id>.json` and `.csv` files. JSON keeps the original `run`, `inputs`, `pages`, raw logits/probabilities, and legacy metadata unchanged, adding a separate `selection` object with settings, stages, reasons, routing scores, labels and metrics. A canonical `source_model_result_sha256` identifies the immutable raw result. CSV contains every page and all original probability columns plus selection flags/reasons and routing score. The original files are never overwritten. Re-export after changing settings; download buttons only represent the currently exported policy.

`./fetch-results.sh` copies all outputs/logs back to WSL. Raw/private artifacts and active settings are not committed to GitHub.

Original policy-layer validation, before semantic v2: 39 automated tests passed. The then-current real 40-page result (`page_router_run_20260924_185941_153783_bd8bb3.json`) was opened in the GUI test harness with `engine.run`, `Router.load`, `Router.classify`, and both SemIf score entry points blocked. Threshold changes altered selection; presets, weights, graph series, labels and sweeps worked; settings survived a fresh GUI session. The source file bytes and all raw probabilities remained unchanged.

Temporary labels `12,20,26,32,40` were used only to verify the software, **not as an accuracy annotation**. At the then-default direct policy, all 40 pages were selected, yielding TP=5, FP=35, TN=0, FN=0 against those temporary labels. Raising the threshold to 1.00 changed selection and correctly updated false negatives. Temporary labels/settings were isolated from the live configuration. Evidence is in `outputs/selection-validation/validation.json` and `logs/selection-real-validation.log`.

Reproduce saved-run-only validation on GX10 without model inference:

```bash
cd ~/kairon-page-router
.venv/bin/python -m pytest tests -q
.venv/bin/python -m app.validate_selection outputs/page_router_run_20260924_185941_153783_bd8bb3.json
```
