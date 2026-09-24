# Semantic-equivalence v2 validation — 24 September 2026

Both benchmark recall targets passed at the shipped requested-data threshold **0.70**, radius 0, with OCR/router automatic inclusion off. Asteron false positives fell from 4 to 1. Runtime increased about 21%; this is a measured tradeoff, not a claim of unchanged performance.

Application prompt version: `direct-options-v2`. Criteria version: `semantic-equivalence-v2`. The unchanged SemIf renderer retains its own `direct-options-v1` identifier in raw distributions. Model: `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`; SemIf commit `23cf1f39fc9534fe81437200959b6dfc7106e45a`. No model, dtype, scoring math, answer ordering, compact compiler, 8192-token limit or vLLM configuration was changed.

## Final exact requested-data criterion

Is at least one requested target value or fact directly available on this page? Equivalent accounting, financial, legal or business synonyms count. Check every requested target: a match to any one target is sufficient. Exact section names are not required. Answer NO only if all targets are absent: nearby totals, components, cash-flow measures, availability, bookings or different periods alone do not count.

**YES:** Yes. At least one requested value or fact can be extracted from this page, including under an equivalent synonym and even alongside other metrics or fiscal periods.

**NO:** No. None of the requested values or facts can be extracted; any information is merely related, uses a different accounting concept or period, or is generic context.

## Method and interpretation

Original PDFs and the shared sparse 10-field JSON/XLSX were read from NicoPC Downloads. All three file hashes for each benchmark match its v1 baseline. Ground truth was used only by post-inference evaluation; it never entered the state, questions, options or prompts. Every exported state was checked against the unchanged template/objective/page text, and every exact prompt hash and token count was checked against SemIf output. All 58 final pages reached real five-row shared scoring, without classification errors or OCR flags.

Eleven generic wording candidates were tested on both benchmarks during this refinement. Long negative lists over-rejected semantic aliases; the final wording explicitly checks every target and accepts any one equivalent match even alongside unrelated measures or periods. No page-number rules, altered probabilities or label-dependent model inputs were used. These are development benchmarks used to refine wording, **not independent held-out accuracy estimates**. Earlier experimental exports remain available; only the two final stems below match the shipped criteria.

## Results and sweeps

### Virelia

Final raw JSON/CSV: `outputs/page_router_run_20260924_230909_138931_deaa8c.json` / `.csv`.
Baseline: `page_router_run_20260924_215713_286366_3f7055.json`.

TP=5; FP=5; TN=30; FN=0; recall=1.000000; precision=0.500000; F1=0.666667; F2=0.833333.
Selected pages: [2, 4, 12, 13, 17, 20, 25, 26, 32, 40].
False-positive pages: [2, 4, 13, 17, 25]. False-negative pages: [].
v1 at the same 0.70 policy: TP=5, FP=5, TN=30, FN=0; FP pages [2, 4, 13, 21, 25].

Model reused: True. Classification 23.748741 s; synchronized model forwards 23.035877 s; mean/page 0.593593 s; preprocessing 0.144091 s. Objective 332 tokens; exact full prompts 826–981 tokens.

| Threshold | TP | FP | TN | FN | Recall | Precision | F1 | F2 | Reduction % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.50 | 5 | 8 | 27 | 0 | 1.0000 | 0.3846 | 0.5556 | 0.7576 | 67.5000 |
| 0.55 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.60 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.65 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.70 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.75 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.80 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.85 | 5 | 5 | 30 | 0 | 1.0000 | 0.5000 | 0.6667 | 0.8333 | 75.0000 |
| 0.90 | 5 | 4 | 31 | 0 | 1.0000 | 0.5556 | 0.7143 | 0.8621 | 77.5000 |
| 0.95 | 5 | 2 | 33 | 0 | 1.0000 | 0.7143 | 0.8333 | 0.9259 | 82.5000 |
| 0.99 | 5 | 1 | 34 | 0 | 1.0000 | 0.8333 | 0.9091 | 0.9615 | 85.0000 |

Full 101-point sweep: `outputs/semantic-evaluation/page_router_run_20260924_230909_138931_deaa8c_evaluation.json` and `.csv`. Highest grid threshold retaining all positives: 0.99. Highest F1/F2 grid thresholds: 0.99 / 0.99.

### Asteron

Final raw JSON/CSV: `outputs/page_router_run_20260924_230933_339425_6a6df8.json` / `.csv`.
Baseline: `page_router_run_20260924_223026_322904_40600e.json`.

TP=6; FP=1; TN=11; FN=0; recall=1.000000; precision=0.857143; F1=0.923077; F2=0.967742.
Selected pages: [4, 7, 9, 11, 12, 13, 17].
False-positive pages: [4]. False-negative pages: [].
v1 at the same 0.70 policy: TP=6, FP=4, TN=8, FN=0; FP pages [2, 3, 4, 16].

Model reused: True. Classification 11.266341 s; synchronized model forwards 10.907618 s; mean/page 0.625778 s; preprocessing 0.080843 s. Objective 332 tokens; exact full prompts 785–1195 tokens.

| Threshold | TP | FP | TN | FN | Recall | Precision | F1 | F2 | Reduction % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.50 | 6 | 2 | 10 | 0 | 1.0000 | 0.7500 | 0.8571 | 0.9375 | 55.5556 |
| 0.55 | 6 | 2 | 10 | 0 | 1.0000 | 0.7500 | 0.8571 | 0.9375 | 55.5556 |
| 0.60 | 6 | 2 | 10 | 0 | 1.0000 | 0.7500 | 0.8571 | 0.9375 | 55.5556 |
| 0.65 | 6 | 2 | 10 | 0 | 1.0000 | 0.7500 | 0.8571 | 0.9375 | 55.5556 |
| 0.70 | 6 | 1 | 11 | 0 | 1.0000 | 0.8571 | 0.9231 | 0.9677 | 61.1111 |
| 0.75 | 4 | 1 | 11 | 2 | 0.6667 | 0.8000 | 0.7273 | 0.6897 | 72.2222 |
| 0.80 | 4 | 0 | 12 | 2 | 0.6667 | 1.0000 | 0.8000 | 0.7143 | 77.7778 |
| 0.85 | 3 | 0 | 12 | 3 | 0.5000 | 1.0000 | 0.6667 | 0.5556 | 83.3333 |
| 0.90 | 3 | 0 | 12 | 3 | 0.5000 | 1.0000 | 0.6667 | 0.5556 | 83.3333 |
| 0.95 | 2 | 0 | 12 | 4 | 0.3333 | 1.0000 | 0.5000 | 0.3846 | 88.8889 |
| 0.99 | 1 | 0 | 12 | 5 | 0.1667 | 1.0000 | 0.2857 | 0.2000 | 94.4444 |

Full 101-point sweep: `outputs/semantic-evaluation/page_router_run_20260924_230933_339425_6a6df8_evaluation.json` and `.csv`. Highest grid threshold retaining all positives: 0.70. Highest F1/F2 grid thresholds: 0.7 / 0.7.

Virelia retains all positives through 0.99 on this sample. Asteron retains all positives at 0.50–0.70; 0.68–0.70 retains six positives with one false positive. At 0.71, two positive pages are lost. Those pages (9 and 17) each score 0.7057850278370112, so the margin above the shipped threshold is small. The shipped threshold remains **0.70**; neither sweep changes it. Asteron page 4 (annual cash-interest disclosure) remains a false positive. The intended semantic distinction is improved, not solved perfectly.

## Performance, memory and residency

Asteron warm classification was 11.266341 s (0.625778 s/page), compared with v1 9.332690 s (0.518483 s/page): **20.7% slower**. The longer criterion-specific suffixes increase work in the unchanged five-row padded suffix batch. Shared prefix reuse and parallel five-criterion scoring remain active. No kernel, quantization, or memory-architecture change was attempted to hide this tradeoff. The initial model load in this resident process took 56.288863 s; both final runs reused it with zero per-run load time.

GX10 unified system memory (GiB; system RAM and CUDA allocations overlap and must not be added):

| Stage | System used | Available | Swap used |
| --- | --- | --- | --- |
| Before router load | 94.553 | 27.074 | 1.682 |
| After router load | 102.900 | 18.727 | 1.682 |
| Before Asteron | 104.749 | 16.878 | 1.682 |
| During Asteron (sampled extrema) | 104.779 | 16.848 | 1.682 |
| After Asteron | 104.761 | 16.866 | 1.682 |

Asteron peak CUDA allocated/reserved: 8.525 / 8.807 GiB. No swap growth. Both models remain resident: router PID 439526, nvidia-smi 9225 MiB; existing `VLLM::EngineCore` PID **3781485**, 87902 MiB, unchanged start time (23 September 20:32:36). Its parent PID 3781282 and command/configuration remain unchanged. Only the isolated prototype processes were restarted during prompt experiments. The GUI is running in the final benchmark process and reuses the same Router singleton.

## Validation and running

46 application tests passed, including exact criterion options/exports, v1/v2 UI provenance, presets, saved-run rescoring with inference forbidden, metrics, immutable exports, objective budgets, and router residency. Final real-run GUI validation changed policies and labels with all SemIf inference entry points blocked; source bytes/probabilities remained unchanged. GUI health endpoint returned `ok`. Evidence: `logs/v2_final_audit.log`, `logs/v2_saved_run_validation.log`, and the per-run logs. The existing small smoke tests remain available.

From `/home/nicot/dev/system_one_model_testing` run `./run.sh`, then open **http://localhost:8507**. Select **Settings → Presets → Benchmark — Direct Fields → Load Preset**; Save Settings persists it. The unchanged old shipped policy was migrated to 0.70 with a backup; custom settings were not overwritten. Active settings live at `/home/kairon/kairon-page-router/config/router_settings.json`.

Open either final saved run. Enter ground truth under **Settings → Benchmark Evaluation**; inspect exact false-positive/false-negative lists under Results. Export Selection Snapshot to include settings and labels without modifying raw inference. The two raw JSON/CSV pairs above, their evaluation JSON/CSV files, and associated logs are available under `/home/kairon/kairon-page-router/` on GX10 and `page-router/` in the WSL repository after `./fetch-results.sh`. Private inputs/artifacts remain gitignored. No production extraction integration was performed.
