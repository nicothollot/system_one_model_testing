# SemIf verification — 2026-09-24

Inspected the current official [SemIf repository](https://github.com/TheoLeeCJ/SemIf), README, `docs/METHOD.md`, and source `core.py`, `direct.py`, `serial.py`, `shared.py`, and packaging metadata before implementing this adapter. Pinned commit: `23cf1f39fc9534fe81437200959b6dfc7106e45a`, package `semif-phase1==0.1.0`.

The recommended CUDA baseline remains `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, BF16. No newer equivalent model was substituted. This is the instruction checkpoint, not `-Base`, a reranker, GGUF, or a fine-tune. The [official model](https://huggingface.co/Qwen/Qwen3.5-4B/tree/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a) is downloaded locally. SemIf selects `Qwen3_5ForCausalLM` and the checkpoint's text configuration; the vision model is not instantiated.

## Verified API and scoring

- `core.load_causal_model(source, revision, device="cuda", dtype="bfloat16")` returns model, tokenizer, metadata. A local path enforces `local_files_only=True`; remote code is disabled.
- `shared.score_shared(model, tokenizer, rows, metadata, max_tokens=8192)` returns result rows and timing. Each row contains `id`, identical `state`, `question`, and described `options`.
- `direct.score(...)` is used for the standalone direct smoke test.
- Options map to uppercase single-token letters. We keep A=yes, B=no and retain option IDs, raw logits, normalized probabilities, and prompt hashes. SemIf takes native vocabulary logits and applies softmax over just the allowed letter logits. There is no generated answer and no parser of generated content.
- SemIf's tokenizer code applies the checkpoint chat template with `add_generation_prompt=True`, `enable_thinking=False`, then encodes without adding special tokens. It checks round-trip single-token slots and answer-boundary consistency. Debug exports preserve the exact resulting prompt for every question.
- Shared mode prefills one exact evidence prefix and uses native `past_key_values.reorder_cache` to branch it into five suffix rows on CUDA. Batched suffixes use explicit attention masks/positions and selective output logits. The five questions reuse page encoding. Different pages are processed sequentially. There is no cross-page prefix cache in this prototype.
- The model must implement selective `logits_to_keep` and a compatible native cache. This model has hybrid attention/recurrent state; blindly treating its cache as ordinary transformer KV tensors would be incorrect. We use upstream's implementation unchanged.
- SemIf also offers `SerialPrefixScorer` using copied branch caches; not needed when shared mode works. There is no silent fallback to generation or repeated fresh inference.

## Environment

SemIf pins torch 2.10.0, transformers 5.17.0, accelerate 1.12.0, safetensors 0.8.0, huggingface-hub 1.31.0, tokenizers 0.23.2, numpy 2.2.6, sentencepiece 0.2.1, protobuf 7.36.1. Installation uses its editable package and preserves those pins.

The [official PyTorch CUDA 13 wheel index](https://download.pytorch.org/whl/cu130/torch/) supplies a Python 3.12 Linux aarch64 wheel for torch 2.10.0. GX10 reports NVIDIA GB10, compute capability 12.1, CUDA driver 13.0. Hardware compatibility is validated by the actual smoke test; SemIf does not publish a separate GB10 certification. Optional custom fast kernels are not installed; the Transformers-supported Torch implementation is used.

Streamlit 1.55.0 conflicts with SemIf's protobuf 7 pin. Streamlit 1.64.0 resolves cleanly and is pinned instead. No vLLM package is installed for the router. Full resolved dependencies are recorded in `requirements-resolved.txt`.

## Interpretation and limitations

These probabilities are conditional option scores, not calibrated estimates of retrieval correctness. They can be sensitive to wording and option order. Upstream reports small BF16 changes between fresh and cached execution, including some argmax changes. See [method](https://github.com/TheoLeeCJ/SemIf/blob/23cf1f39fc9534fe81437200959b6dfc7106e45a/docs/METHOD.md) and [results](https://github.com/TheoLeeCJ/SemIf/blob/23cf1f39fc9534fe81437200959b6dfc7106e45a/docs/RESULTS.md).

The four-page synthetic test checks operation, not real-document recall or calibration. Establish those with labeled PDFs and field-specific false-negative review. Thresholds in the GUI are simulations, not a production recommendation. Sparse text pages require manual visual/OCR review even if the text classifier assigns a low score.
