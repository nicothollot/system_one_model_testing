# Compact-objective fix: original 40-page / 80-field regression

Validated on GX10, 2026-09-24. The original failure artifact was `page_router_run_20260924_182157_946003_01fa69.json`: 40 pages, zero scored, zero model-forward seconds. Complete JSON instructions and duplicate workbook headers inflated every prompt to roughly 15,000 tokens against an 8,192-token cap.

## Change

The deterministic compiler retains every requested field, groups fields by source section, preserves meaningful types/units and field-specific constraints, and removes narrow downstream output boilerplate. All 80 workbook header cells are deduplicated against the JSON. The two completion-specific constraints remain intact. No model, SemIf revision, generation mode, or token-cap substitution was made.

The exact local tokenizer checks the objective (maximum 3,072 tokens) and all five full prompts for every page before loading the model or classifying. At least 256 tokens of prompt headroom are required. Rejected specifications produce a `FAILED_INPUT_PREPARATION` export with a run-level error, not a misleading successful zero-page selection. Runtime failures use router-review fields and never change OCR flags. Failed/partial runs cannot display threshold reduction statistics.

Full original JSON, parsed XLSX, and page text remain preserved separately from `compiled_routing_objective`. Compilation records include field provenance and removed-boilerplate audit details.

## Original-file verification

The PDF was located in NicoPC Downloads; JSON and XLSX were read from the existing local benchmark files without modifying their repository. All three SHA-256 hashes matched the failed run's recorded input hashes. The files were copied privately to GX10, freshly parsed, and rerun. All 40 extracted page texts exactly match the original failure artifact. This was not a reconstruction from synthetic replacement pages.

## Results

| Check | Result |
|---|---:|
| Requested / compiled fields | 80 / 80 |
| Duplicate XLSX headers removed | 80 |
| Compiled objective tokens | **1,631** |
| Page text tokens | 283–370 |
| Exact full-prompt tokens (all 200 questions) | **2,150–2,259** |
| Minimum token headroom | **5,933** |
| Pages successfully scored | **40 / 40** |
| Run status | **COMPLETED** |
| Model-forward seconds | **39.039486** |
| Classification seconds | **40.488481** |
| Average page seconds | **1.012072** |
| Median page seconds | **1.005019** |
| Fastest page | 5: 0.982620 s |
| Slowest page | 25: 1.175540 s |
| PDF preprocessing | 0.151243 s |
| Application context preflight | 0.382207 s |
| Warm end-to-end run | 41.152833 s |

All five distributions exist on all pages; every probability is finite, within [0,1], and normalized. All 400 probabilities round-trip exactly through CSV. Every actual SemIf `input_tokens` value equals its preflight exact-token count. All 40 OCR flags and all 40 router-review flags are false. Original JSON and parsed XLSX are unchanged in the new debug export.

The same resident model also passed the original small four-page application fixture and a new generated 80-field/four-page inference regression. That larger synthetic objective measured 1,777 tokens, prompts 2,020–2,039 tokens, scored 4/4 pages, and recorded 3.635741 model-forward seconds. No mock inference was used for these three runs. Sixteen automated tests passed, including exact-token budget tests using the installed Qwen tokenizer, semantic-constraint preservation, failure-before-model-loading, OCR flag invariance, and zero/partial-run GUI behavior.

The updated GUI was relaunched as PID 280954 and its live health endpoint passed. Streamlit's application test harness rendered the actual new 40-page artifact and exercised its threshold/neighbor controls; it also rendered the original failed artifact and verified that all selection simulators were absent and `FAILED_CLASSIFICATION` was prominent. Evidence: `logs/regression-gui-validation.json`.

## Unified memory and existing server

| Stage | Used GiB | Available GiB | Swap GiB |
|---|---:|---:|---:|
| Before router load | 94.209 | 27.418 | 1.682 |
| After router load | 102.890 | 18.737 | 1.682 |
| Load peak / minimum available | 110.746 | 10.881 | 1.682 |
| Before real 40-page classification | 105.015 | 16.613 | 1.682 |
| Classification peak / minimum available | 105.652 | 15.975 | 1.682 |
| After classification, model resident | 105.652 | 15.975 | 1.682 |

CUDA peak allocated during the 40-page run: 8.637 GiB; peak reserved: 9.650 GiB. These overlap system memory. Swap did not grow. Model load took 63.089 s once, before the small fixture, and the loaded model was reused for both larger tests.

`VLLM::EngineCore` remained PID **3781485**, creation timestamp **1790209956.73**, and reported **87,902 MiB**. Its parent server remained PID **3781282**. No vLLM requests, signals, configuration/model changes, or installation modifications occurred. Only the prototype's own old GUI process was stopped to apply its code update.

## Review artifacts

GX10 base: `/home/kairon/kairon-page-router/`.

- **Real 40-page JSON:** `outputs/page_router_run_20260924_184313_398225_860061.json`
- **Real 40-page CSV:** `outputs/page_router_run_20260924_184313_398225_860061.csv`
- Real run log: `logs/page_router_run_20260924_184313_398225_860061.log`
- All three regression runs: `outputs/regression-validation.json`
- Regression stdout: `logs/regression-real.log`
- Unit-test evidence: `logs/regression-unit-tests.log`
- Synthetic 80-field run: `outputs/page_router_run_20260924_184309_502821_71b55d.json`
- Small fixture: `outputs/page_router_run_20260924_184202_410261_fa8906.json`

Copies of outputs/logs are available under the repository's `page-router/outputs/` and `page-router/logs/`. Raw benchmark files and artifacts remain gitignored/private. Use `./fetch-results.sh` after future GUI runs.

This verifies that every page reaches actual inference and that the compact specification fixes the context-length failure. It does not establish recall or calibrate a threshold: the real run's overall YES scores range from approximately 0.133 to 0.999, so false-negative inspection remains necessary. No OCR, production integration, or downstream extraction was added.
