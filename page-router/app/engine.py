"""GX10-only resident SemIf adapter and benchmark orchestration."""
from app import criteria
import datetime as dt
import fcntl
import gc
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import platform
import statistics
import threading
import time
import uuid

from app import data
from app.objective import compile_objective
from app.preparation import MAX_TOKENS, prepare_pages
from app.monitor import Monitor, command, guard, snapshot

MODEL = "Qwen/Qwen3.5-4B"
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
SEMIF_COMMIT = "23cf1f39fc9534fe81437200959b6dfc7106e45a"
ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "Qwen3.5-4B"


def offline():
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        os.environ[key] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def logger(stem):
    (ROOT / "logs").mkdir(exist_ok=True)
    log = logging.getLogger(stem)
    log.setLevel(logging.INFO)
    if not log.handlers:
        handler = logging.FileHandler(ROOT / "logs" / f"{stem}.log")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    return log


class Router:
    def __init__(self):
        offline()
        if platform.node() != "gx10-fbb7":
            raise RuntimeError("Inference is restricted to gx10-fbb7. Run ./run.sh from WSL.")
        self.lockfile = (ROOT / ".router.lock").open("w")
        try:
            fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another router process owns the model. Use its GUI; do not start a second model.") from exc
        self.lock = threading.Lock()
        self.model = None
        self.load_seconds = 0
        self.log = logger("router-service")
        self.log.info("Application start: host=%s python=%s; no external inference configured", platform.node(), platform.python_version())

    def get_tokenizer(self):
        if not hasattr(self, "tokenizer"):
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True, trust_remote_code=False)
        return self.tokenizer

    def load(self, progress=lambda message: None):
        if self.model is not None:
            progress("Model already loaded; reusing resident router")
            return False
        import torch
        from semif_phase1.core import load_causal_model
        self.torch = torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; no CPU/local inference fallback is permitted")
        if not MODEL_PATH.is_dir() or not (MODEL_PATH / "config.json").exists():
            raise FileNotFoundError(f"Local model missing at {MODEL_PATH}; run setup-remote.sh while online")
        commit = command(["git", "-C", str(ROOT / "vendor/SemIf"), "rev-parse", "HEAD"]).strip()
        if commit != SEMIF_COMMIT:
            raise RuntimeError(f"SemIf commit mismatch: {commit}")
        manifest = json.loads((MODEL_PATH / "router-manifest.json").read_text())
        if manifest != {"model": MODEL, "revision": REVISION}:
            raise RuntimeError("Model provenance manifest does not match pinned checkpoint")
        self.before = snapshot(torch, commands=True)
        self.log.info("Before load: %s", json.dumps(self.before))
        guard(18)
        progress("Model loading on GX10 CUDA")
        started = time.perf_counter()
        monitor = Monitor(torch).start()
        try:
            self.model, self.tokenizer, self.metadata = load_causal_model(str(MODEL_PATH), REVISION, device="cuda", dtype="bfloat16")
            torch.cuda.synchronize()
            guard(8, self.before["swap_used_bytes"])
        except Exception:
            self.model = None
            gc.collect()
            torch.cuda.empty_cache()
            self.log.exception("Model load failed; existing vLLM untouched")
            raise
        finally:
            self.load_memory = monitor.stop()
            self.log.info("Load attempt memory=%s final=%s", json.dumps(self.load_memory), json.dumps(snapshot(torch, commands=True)))
        self.load_seconds = time.perf_counter() - started
        self.after_load = snapshot(torch, commands=True)
        self.metadata.update(model=MODEL, model_revision=REVISION, semif_commit=SEMIF_COMMIT,
                             semif_version=importlib.metadata.version("semif-phase1"), backend="torch / SemIf shared",
                             cuda_version=torch.version.cuda, device_name=torch.cuda.get_device_name(0),
                             capability=list(torch.cuda.get_device_capability(0)), python=platform.python_version())
        self.log.info("Model loaded in %.6fs metadata=%s after=%s", self.load_seconds, json.dumps(self.metadata), json.dumps(self.after_load))
        return True

    def classify(self, page):
        from semif_phase1.shared import score_shared
        started = time.perf_counter()
        try:
            guard(8, self.before["swap_used_bytes"])
            results, timing = score_shared(self.model, self.tokenizer, page["classifier_rows"], self.metadata, max_tokens=MAX_TOKENS)
            page.update(raw_distributions=results, semif_timing=timing)
            scores = {key: dict(zip(result["option_ids"], result["probabilities"])) for key, result in zip(data.QUESTIONS, results)}
            data.validate_scores(scores)
            page.update(scores=scores, raw_distributions=results, semif_timing=timing, classification_status="scored")
        except ValueError as exc:
            page.update(exception=str(exc), classification_error=str(exc), classification_status="unscored", needs_router_review=True)
        finally:
            page["classification_seconds"] = time.perf_counter() - started
        return page


def run(router, pdf_name, pdf_bytes, json_bytes, xlsx_bytes, progress=lambda message: None, input_names=None):
    if not router.lock.acquire(blocking=False):
        raise RuntimeError("Router is busy with another analysis; retry after it finishes")
    started = time.perf_counter()
    stem = "page_router_run_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:6]
    log = logger(stem)
    log.info("Run start; GX10 connection established via local backend: %s", platform.node())
    monitor = None
    try:
        guard(8)
        progress("File parsing: JSON and reference XLSX")
        mark = time.perf_counter()
        instructions, reference = data.parse_json(json_bytes), data.parse_xlsx(xlsx_bytes)
        compilation = compile_objective(instructions, reference)
        objective = compilation["compiled_routing_objective"]
        parsing_seconds = time.perf_counter() - mark
        log.info("PDF preprocessing start")
        progress("PDF preprocessing: extracting every page")
        mark = time.perf_counter()
        pages = data.preprocess(pdf_bytes)
        preprocessing_seconds = time.perf_counter() - mark
        log.info("PDF preprocessing end: pages=%d seconds=%.6f", len(pages), preprocessing_seconds)
        progress("Input preparation: compiling objective and checking every exact prompt token budget")
        token_budget = prepare_pages(router.get_tokenizer(), pages, objective)
        log.info("Routing compilation: fields=%d XLSX_duplicates=%d token_budget=%s", compilation["requested_field_count"],
                 compilation["xlsx_duplicates_removed"], json.dumps(token_budget))
        progress(f"Input preparation: objective {token_budget['routing_objective_tokens']} tokens; "
                 f"prompts {token_budget['exact_prompt_tokens_min']}–{token_budget['exact_prompt_tokens_max']}; "
                 f"minimum headroom {token_budget['available_token_headroom_min']}")
        cold, classification_seconds, memory = False, 0, None
        input_errors = token_budget["input_preparation_errors"]
        if input_errors:
            error = "INPUT PREPARATION FAILED: " + " ".join(input_errors)
            log.error(error)
            progress(error)
            for page in pages:
                page.update(classification_status="not_attempted", classification_error=error, exception=error, needs_router_review=True)
            before_run = after_run = snapshot(getattr(router, "torch", None), commands=True)
        else:
            cold = router.load(progress)
            before_run = snapshot(router.torch, commands=True)
            log.info("Runtime=%s before_load=%s after_load=%s before_classification=%s", json.dumps(router.metadata),
                     json.dumps(router.before), json.dumps(router.after_load), json.dumps(before_run))
            monitor = Monitor(router.torch).start()
            mark = time.perf_counter()
            aborted = None
            for index, page in enumerate(pages):
                progress(f"Classification: page {index + 1} / {len(pages)} — five shared-state probability questions")
                if aborted:
                    page.update(classification_status="not_attempted", classification_error=aborted, exception=aborted, needs_router_review=True)
                    continue
                try:
                    router.classify(page)
                except Exception as exc:
                    aborted = f"{type(exc).__name__}: {exc}"
                    page.update(exception=aborted, classification_error=aborted, classification_status="error", needs_router_review=True)
                    log.exception("Classification aborted; no generation or CPU fallback; vLLM untouched")
                    gc.collect()
                    router.torch.cuda.empty_cache()
                log.info("Page %d seconds=%.6f probabilities=%s warning=%s exception=%s", page["page"], page["classification_seconds"],
                         json.dumps(page["scores"]), page["text_extraction_warning"], page.get("classification_error"))
            classification_seconds = time.perf_counter() - mark
            memory = monitor.stop()
            monitor = None
            after_run = snapshot(router.torch, commands=True)
        durations = [(p["page"], p["classification_seconds"]) for p in pages if p["classification_status"] == "scored"]
        times = [value for _, value in durations]
        complete = len(times) == len(pages)
        status = "FAILED_INPUT_PREPARATION" if input_errors else "COMPLETED" if complete else "FAILED_CLASSIFICATION" if not times else "PARTIAL_CLASSIFICATION"
        metadata = getattr(router, "metadata", {"model": MODEL, "model_revision": REVISION, "semif_commit": SEMIF_COMMIT,
                                                "backend": "torch / SemIf shared", "device": "cuda:0 (inference not attempted)"})
        result = {
            "run": {"timestamp": dt.datetime.now(dt.timezone.utc).isoformat(), "pdf": pdf_name, **metadata,
                    "prompt_version": criteria.PROMPT_VERSION, "classifier_criteria_version": criteria.CRITERIA_VERSION, "schema_version": 2, "hostname": platform.node(), "total_pages": len(pages), "scored_pages": len(times), "status": status,
                    "classification_error": " ".join(input_errors) if input_errors else None,
                    "selection_statistics_valid": complete, "unscored_pages": [p["page"] for p in pages if not p.get("scores")],
                    **token_budget, "objective_compiler_version": compilation["version"],
                    "model_load_seconds": router.load_seconds, "model_load_seconds_this_run": router.load_seconds if cold else 0,
                    "model_reused": not cold and router.model is not None, "input_parsing_seconds": parsing_seconds,
                    "preprocessing_seconds": preprocessing_seconds, "classification_seconds": classification_seconds,
                    "context_preparation_seconds": sum(p.get("context_preparation_seconds", 0) for p in pages),
                    "model_forward_seconds": sum(p.get("semif_timing", {}).get("prefill_seconds", 0) + p.get("semif_timing", {}).get("suffix_forward_seconds", 0) for p in pages),
                    "average_page_seconds": statistics.mean(times) if times else None, "median_page_seconds": statistics.median(times) if times else None,
                    "fastest_page": dict(zip(("page", "seconds"), min(durations, key=lambda pair: pair[1]))) if times else None,
                    "slowest_page": dict(zip(("page", "seconds"), max(durations, key=lambda pair: pair[1]))) if times else None,
                    "approx_total_page_tokens": sum(p["approx_tokens"] for p in pages),
                    "exact_total_page_tokens": sum(p.get("tokens", 0) for p in pages),
                    "shared_prefix_tokens_processed": sum(p.get("semif_timing", {}).get("prefix_tokens", 0) for p in pages),
                    "suffix_tokens_processed": sum(p.get("semif_timing", {}).get("padded_suffix_tokens", 0) for p in pages),
                    "memory_before": getattr(router, "before", None), "memory_after_load": getattr(router, "after_load", None), "memory_during_load": getattr(router, "load_memory", None),
                    "memory_before_classification": before_run, "memory_during_classification": memory, "memory_after_run": after_run,
                    "max_prompt_tokens": MAX_TOKENS, "log": str(ROOT / "logs" / f"{stem}.log"),
                    "probability_status": "Uncalibrated probabilities conditional on declared A=yes/B=no options; no generation.",
                    "threshold_rule": "strictly greater than threshold; document selection statistics disabled unless every page is scored",
                    "vllm_processes_unchanged": before_run["vllm_processes"] == after_run["vllm_processes"]},
            "inputs": {"instructions_json": instructions, "parsed_reference_fields": reference,
                       "compiled_routing_objective": objective, "routing_objective_compilation": compilation,
                       "classifier_template": data.TEMPLATE,
                       "filenames": input_names or {"pdf": pdf_name},
                       "sha256": {"pdf": data.fingerprint(pdf_bytes), "json": data.fingerprint(json_bytes), "xlsx": data.fingerprint(xlsx_bytes)}},
            "threshold_summary": data.thresholds(pages), "pages": pages,
        }
        progress("Result creation: JSON and CSV export")
        mark = time.perf_counter()
        data.export(result, ROOT / "outputs", stem)
        result["run"]["export_seconds"] = time.perf_counter() - mark
        result["run"]["total_seconds"] = time.perf_counter() - started
        result["run"]["timing_scope"] = "Total ends after initial export; excludes final metadata rewrite and browser rendering. Context preparation is preflight; page times measure shared scoring and readout; model_forward_seconds measures synchronized prefill+suffix only."
        data.export(result, ROOT / "outputs", stem)
        log.info("Totals=%s", json.dumps(result["run"]))
        return result
    except Exception:
        log.exception("Run failed")
        raise
    finally:
        if monitor:
            monitor.stop()
        router.lock.release()
        for handler in list(log.handlers):
            handler.close()
            log.removeHandler(handler)
