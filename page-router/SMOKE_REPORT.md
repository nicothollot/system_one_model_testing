# Real GX10 validation — 2026-09-24

**Passed:** eight automated tests, real CUDA direct SemIf scoring, five-question shared scoring for all four synthetic PDF pages, JSON/CSV validation, and GUI rendering/simulator tests. Normal application inference is exclusively on `gx10-fbb7`.

The live GUI launched as PID `240543`, served its health endpoint successfully, and returned HTTP 200 through a private SSH tunnel tested from WSL. The actual exported smoke result also rendered successfully through Streamlit's application test harness, including interactive threshold and neighbor changes. JSON and CSV contain all 40 probability values with exact float round-trip agreement. `pip check` reported no broken dependencies. No manual visual browser inspection was performed.

## Provenance

- Model: `Qwen/Qwen3.5-4B`, BF16 text model.
- Revision: `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- SemIf: `semif-phase1==0.1.0`, commit `23cf1f39fc9534fe81437200959b6dfc7106e45a`.
- Python 3.12.3, Torch 2.10.0+cu130, CUDA 13.0, Transformers 5.17.0, NVIDIA GB10 capability 12.1.
- Source/dependencies and model live under `/home/kairon/kairon-page-router`; no system Python or existing vLLM installation was modified.

Torch emits a capability-range warning (reported maximum 12.0 versus GB10 12.1), but actual model loading, direct logits and shared-cache inference passed. The warning remains visible in logs; no version substitution or custom kernel patch was required.

## Results

Direct smoke: `P(yes)=0.9997388096809043`, `P(no)=0.0002611903190957194`, with zero generated tokens. Python TCP socket connections were blocked during this successful smoke, in addition to offline environment flags and local-only model loading. This checks Python application network independence; it is not an OS-wide network-isolation claim.

| Synthetic page | Overall YES |
|---|---:|
| Tree survey count and date | 0.9998766054240137 |
| Survey methodology and exclusions | 0.9902915235185259 |
| Unrelated cafeteria menu | 0.0021827164453451808 |
| Blank page | 0.34864513533394575 |

The blank page is explicitly flagged for visual/OCR review. Its probability is not grounds for rejection. Every page contains all five distributions with finite probabilities summing to one. At threshold >0.50, raw selection is pages 1–2; ±1 expansion yields pages 1–3, and page 4 remains separately flagged for manual review.

## Timing

| Measurement | Seconds |
|---|---:|
| Model load | 61.267343 |
| PDF preprocessing | 0.008071 |
| Four-page classification | 1.618987 |
| Mean page | 0.404093 |
| Median page | 0.394334 |
| Synchronized model forward total | 1.528299 |
| Warm application run, including exports | 1.721166 |

The model was loaded before the separate direct smoke, then reused by the four-page application run. Therefore this run's total excludes model loading. These short synthetic pages contain only 132 extracted-text tokens altogether; do not extrapolate this throughput to long PDF pages or large objectives. Each page's five criteria shared one prefix (401–451 tokens) with five suffix branches.

## Unified memory

| Stage | System used GiB | Available GiB | Swap GiB |
|---|---:|---:|---:|
| Before router load | 93.967 | 27.660 | 1.682 |
| After router load | 102.717 | 18.910 | 1.682 |
| Load peak / minimum available | 110.494 | 11.133 | 1.682 |
| Before page classification | 103.669 | 17.958 | 1.682 |
| Classification peak / minimum available | 104.355 | 17.272 | 1.682 |
| After classification, model still loaded | 104.355 | 17.272 | 1.682 |

CUDA allocated after load: 7.834 GiB; during classification peak: 8.356 GiB; reserved peak: 8.490 GiB. These overlap system memory and must not be added to it. The successful smoke had **no swap growth**. Model-load transient allocations were larger than steady-state model usage.

The initial cold attempt was stopped by the 256 MiB swap-growth guard after roughly 365 MiB growth. It performed no classification and unloaded only the router. After memory settled with 17 GiB physically free and no active paging, one retry with **unchanged guard limits** passed. Initial installation/download also coincided with a rise in swap from about 208 MiB to 1.3 GiB; the prototype did not change swap configuration. Failed and successful logs are both preserved. Future cold loads can still be rejected if memory conditions change.

## Existing workload

Before setup and after smoke, `VLLM::EngineCore` remained PID `3781485`, started 2026-09-23 20:32:36, with the same reported 87,902 MiB GPU allocation. Its parent vLLM server remained PID `3781282`. Command/configuration continued to reference `Qwen/Qwen3.8-27B-FP8`. No stop, restart, kill, configuration/model/install change, or inference request was issued to that server.

## Artifacts

Remote prefix: `/home/kairon/kairon-page-router/`.

- `outputs/page_router_run_20260924_181421_538247_99071e.json`
- `outputs/page_router_run_20260924_181421_538247_99071e.csv`
- `outputs/direct-smoke.json`
- `logs/page_router_run_20260924_181421_538247_99071e.log`
- `logs/router-service.log`
- `logs/smoke.log` (guarded failure)
- `logs/smoke-retry.log` (successful run)
- `samples/tiny.pdf`, `samples/instructions.json`, `samples/reference.xlsx`

These were copied to corresponding `page-router/outputs`, `page-router/logs`, and `page-router/samples` directories in the WSL repository. All are gitignored; this report is versionable.

The CLI smoke exits after validation and releases its model. The GUI loads on first analysis and retains that model across subsequent runs; reopening saved results needs no model. Real-document recall, calibration, concurrent extraction latency and OCR remain unmeasured.
