# PDF page selection benchmark

This is a standalone R&D application. It parses three files, constructs request-specific context, and scores five relevance questions for every PDF page using SemIf's direct native option logits. It performs no downstream field extraction and has no connection to the existing vLLM endpoint.

## Installation and architecture

Source lives in `/home/nicot/dev/system_one_model_testing` on NicoPC WSL. The full application runs on GX10; the browser connects through SSH. No local model environment or weights are installed on NicoPC. Its only runtime dependencies are Bash, SSH and, for synchronization, rsync.

GX10 project: `/home/kairon/kairon-page-router`.
Isolated Python 3.12 venv: `/home/kairon/kairon-page-router/.venv`.
SemIf source: `/home/kairon/kairon-page-router/vendor/SemIf`.
Model: `/home/kairon/kairon-page-router/models/Qwen3.5-4B` (about 8.8 GiB on disk).

The installed model is `Qwen/Qwen3.5-4B` revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. SemIf is version 0.1.0 at commit `23cf1f39fc9534fe81437200959b6dfc7106e45a`. Inference uses BF16 Torch CUDA, the native Qwen text architecture and five batched suffixes sharing a page prefix. Important versions are pinned by SemIf and `requirements.txt`; `requirements-resolved.txt` records the complete environment. See [research notes](RESEARCH.md) for API and architectural details.

For installation from WSL, run `./setup-remote.sh` in the repository root. It creates only the router directory/venv, clones the pinned source, installs dependencies, and downloads the exact model snapshot. It neither installs router vLLM nor modifies system Python. Initial setup needs internet for packages and weights, without credentials.

## Running

From `/home/nicot/dev/system_one_model_testing`:

```bash
./run.sh
```

Open `http://localhost:8507`. Select exactly the PDF, instructions JSON and reference XLSX, then **Analyze Pages**. First analysis loads the model; later analyses reuse the same process and model. One analysis runs at a time. Closing the SSH tunnel leaves the remote GUI/model process alive; running the command again reconnects. A process lock prevents a second router model instance. The first connection requires GX10 to have at least 18 GiB available before loading; analysis requires at least 8 GiB available.

The GUI contains all five YES/NO distributions, sortable columns, a page-number relevance graph, exact state/question/options/chat prompts, raw logits, extraction warnings and exceptions. Threshold and ±1-neighbor controls operate solely on stored results. The default 0.50 is an experimental slider position, not a recommended production cutoff. Comparisons use `probability > threshold` consistently.

Input JSON must be a nonempty object/array. Complete original JSON, parsed workbook cells (including formula text/cached values), and every page's extracted text remain in the debug export. These originals are **not** appended to classifier state. `app/objective.py` deterministically compiles the smaller `compiled_routing_objective`: field names, section cues, useful types/units, and field-specific semantic constraints. Fields are grouped by section; section labels are relevance cues, not exclusive page filters. No requested field is truncated or dropped.

The compiler supports named records under `entries`, `fields`, `requested_fields`, or `targets`, simple field-name lists, and keyed field mappings. It recognizes `Use the ... section` cues and explicit source/section properties. It removes narrowly recognized downstream output/format boilerplate, removes redundant units already in field names, merges tabular workbook definitions into matching JSON fields, and deduplicates repeated header-only workbook cells. Unknown semantic text/properties are retained; unsupported field records fail explicitly. Compilation audit data includes all preserved records/provenance and removed boilerplate. No LLM or heuristic summarization call is involved.

Before loading the model or scoring any page, the local Qwen tokenizer measures the compiled objective and every complete chat-template prompt. The objective budget is **3,072 tokens**, the full-prompt cap remains **8,192**, and every prompt must retain at least **256 tokens of headroom**. If any check fails, the run is exported as `FAILED_INPUT_PREPARATION` with a run-level error directing further compaction/review. No inference or silent truncation occurs. JSON/CSV and the GUI show `routing_objective_tokens`, `page_text_tokens`, `exact_prompt_tokens` (all five questions in JSON), and `available_token_headroom`.

`needs_visual_or_ocr_review` describes PDF/text quality only. Classifier failures use `classification_status`, `classification_error`, and `needs_router_review`. Zero scored pages yield `FAILED_CLASSIFICATION`; incomplete scoring yields `PARTIAL_CLASSIFICATION`. The GUI prominently reports the scored/total count and unscored pages, explains that zero selected pages does not mean zero relevant pages, and disables all threshold/reduction statistics until every page has a valid distribution. Legacy failed exports receive the same protective display.

Use **Inspect a saved run** to reopen previous exports (including the smoke test) without loading the model. Input size guards reject JSON over 2 MiB, or workbooks over 100,000 populated cells / 2 MiB of populated text, without truncating them.

## Offline and privacy

Normal launch sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `DO_NOT_TRACK=1`, and disables Streamlit usage reporting. The loader uses a local path, `local_files_only=True`, `trust_remote_code=False`. No external inference, analytics, remote logs, hosted plotting, OCR service, or extractor endpoint is configured. Charts are rendered by the local application. The service listens only on GX10 loopback; SSH forwards to NicoPC loopback. Use an already functioning LAN/Tailscale route when public internet is disconnected; new Tailscale connection establishment may depend on your network configuration.

Do not run the setup/download script during offline operation. Weights and dependencies must already be installed. Documents and debug prompts are sensitive: uploads remain in process memory; complete text/context is intentionally written to local run JSON. Outputs/logs/samples/model directories are gitignored. `fetch-results.sh` transfers results only to NicoPC through SSH. Retain or delete these local debug artifacts according to your needs.

## Exports and logs

Every completed, partially classified, or token-budget-rejected run automatically writes:

```text
/home/kairon/kairon-page-router/outputs/page_router_run_<UTC timestamp>_<id>.json
/home/kairon/kairon-page-router/outputs/page_router_run_<UTC timestamp>_<id>.csv
/home/kairon/kairon-page-router/logs/page_router_run_<UTC timestamp>_<id>.log
```

Download JSON/CSV from the GUI or run `./fetch-results.sh` from WSL. Local copies go to `page-router/outputs/` and `page-router/logs/`. CSV preserves Python float precision, with both probabilities for each question; JSON also preserves complete inputs, every page, exact prompts, raw SemIf results, memory samples, runtimes and provenance. The GUI shows six decimal places without rounding stored scores.

Service stdout: `logs/gui.log`; model lifecycle: `logs/router-service.log`; installation/download logs and `logs/smoke.log` also remain local. No giant model tensors are logged.

## Memory and timings

System RAM availability is authoritative for GB10 unified memory. Do not add CUDA allocation to system used RAM: they overlap. `nvidia-smi` does not provide a normal discrete-VRAM capacity here. Each run records raw `free -h`/`nvidia-smi`, system used/available/swap, process RSS, allocated/reserved CUDA memory and sampled peak/minimum values. Samples are taken every 250 ms during model load and classification; transient system peaks between samples can be missed. CUDA allocator peaks are also captured.

Before model load, an 18 GiB available-memory guard reserves room for weights and work buffers. Between pages, at least 8 GiB must remain available. Growth of swap by more than 256 MiB relative to pre-load baseline aborts further router work. An allocation failure aborts classification, records unknown pages and exports partial results; it never kills/reconfigures the existing server or retries with CPU/generation. These checks are conservative guardrails, not a hard OS memory partition: other workloads can change available memory during a forward pass. Long contexts are capped at 8,192 tokens with explicit rejection and no truncation to bound memory use.

The existing Qwen3.8-27B-FP8 vLLM service and its installation/configuration were left untouched. No requests are sent to it. Run metadata compares EngineCore PID/creation time before and after classification. Co-residency does not establish zero performance interference under simultaneous heavy workloads.

Observed successful smoke: load 61.267 s; four-page PDF preprocessing 0.0081 s; classification 1.619 s (404 ms/page). Available RAM: 27.66 GiB before load, 18.91 GiB after load, minimum 17.27 GiB during classification, 17.27 GiB after. The load itself briefly reached 11.13 GiB available. System-used RAM rose by 8.75 GiB after loading; CUDA weights occupied 7.83 GiB, with an 8.36 GiB allocated peak during classification. Swap remained at 1.682 GiB during the successful attempt. The first attempt aborted because swap grew by about 365 MiB; it is retained in the logs. See [full smoke report](SMOKE_REPORT.md).

Timings separate model lifetime load, load cost in the current run (zero when reused), file parsing/compilation, PDF preprocessing, exact-context preparation/preflight, synchronized prefill/suffix inference, whole-page classification, export and total. Classification includes SemIf encoding/readout but excludes the earlier application preflight; forward time is a subset, not an additional cost. Total ends after initial export, excluding the final metadata rewrite/browser rendering. Exact page token counts use the model tokenizer; approximate counts use ceil(characters/4). Shared prefix and padded suffix processed-token counts are reported separately.

## Tests

Unit tests (no inference) on GX10:

```bash
ssh gx10 'cd ~/kairon-page-router && .venv/bin/python -m pytest tests -q'
```

Real offline CUDA smoke test, when no other router process has loaded its model:

```bash
ssh gx10 'cd ~/kairon-page-router && .venv/bin/python -m app.smoke'
```

This creates four synthetic pages (direct data, supporting methodology, unrelated cafeteria text, blank page), a nonfinancial JSON request and reference workbook, exercises direct and shared SemIf inference, validates every distribution/export and checks EngineCore continuity. Synthetic evidence is in `samples/`; direct scores are in `outputs/direct-smoke.json`. Use the same three sample files in the GUI for a repeatable interactive run.

The larger regression preserves the small fixture, generates a synthetic 80-field request with repeated instructions and duplicate workbook headers, then reruns the original real benchmark. With the prototype GUI's model process stopped (leave the 27B service alone), run on GX10:

```bash
cd ~/kairon-page-router
.venv/bin/python -m app.regression \
  --pdf samples/virelia-q4-2026-quarterly-report.pdf \
  --instructions samples/virelia-q4-2026.instructions.json \
  --reference samples/virelia-q4-2026-80-field-reference.xlsx \
  --source-run outputs/page_router_run_20260924_182157_946003_01fa69.json
```

This checks original-file hashes and page text, actual model-forward timings on every page, probability/CSV round trips, token headroom, OCR-flag invariants, and vLLM process continuity. Validation manifest: `outputs/regression-validation.json`. See [40-page regression report](REGRESSION_REPORT.md) for the observed results. Files remain private and gitignored.

## Limitations and troubleshooting

- **SSH failure:** verify `ssh gx10 hostname` returns `gx10-fbb7` from ordinary WSL. The sandbox initially could not read a system SSH configuration with its expected ownership; authorized SSH outside that sandbox worked. No SSH configuration or password was changed. Check Tailscale/reachability and the existing SSH alias.
- **Port 8507 busy:** reuse the already running tunnel, or close your previous tunnel. The launcher will not replace an occupied service. GX10 serves loopback only.
- **Model missing:** run `./setup-remote.sh` while online. The loader checks the local provenance manifest and fails instead of reaching the Hub at runtime.
- **CUDA unavailable:** verify `nvidia-smi` and the venv's CUDA Torch installation. Inference is deliberately rejected on any host other than `gx10-fbb7`; there is no local/CPU fallback.
- **GB10 warning:** Torch 2.10 emits a warning that its reported maximum capability is 12.0 while GB10 is 12.1. Inspect the recorded real inference smoke outcome before treating compatibility as established. No alternate Torch version is silently installed.
- **OOM or insufficient unified memory:** review snapshots and the manual-review queue. Wait for available memory or use smaller input contexts. Do not stop/change the existing 27B service to make room automatically. A concurrent change elsewhere on GX10 may trigger the conservative swap guard.
- **Malformed inputs:** GUI explains JSON, workbook or PDF parse errors; see the run log. No fabricated distributions are produced. Decrypt password-protected PDFs outside the app first.
- **Text extraction failure/blank scan:** page remains represented and flagged `needs_visual_or_ocr_review`; text-only probabilities cannot assess missing visual evidence. OCR is not implemented.
- **Context too long:** inspect the compiled objective and compiler audit. Objectives over 3,072 tokens, or prompts without 256 tokens of headroom below 8,192, fail the entire run at input preparation with exact diagnostics. Full fields/prompts are retained. No threshold/reduction estimates are shown for failed/partial results. Unknown constraints may require additional deterministic compiler rules; no truncation or chunking is applied automatically.
- **Quality:** fixed A/B option order, wording and BF16 shared-cache execution can affect scores. Probabilities are not calibrated. Real-PDF recall, false negatives, concurrent-load latency and long-document throughput need separate measurement. No production threshold is chosen.

Main implementation: `app/data.py` (parsing/export/simulation), `app/objective.py` (compact compiler), `app/preparation.py` (token preflight), `app/engine.py` (resident model and benchmark), `app/monitor.py` (memory), `gui.py` (UI), `app/smoke.py`, `app/regression.py`, and `tests/` (validation).
