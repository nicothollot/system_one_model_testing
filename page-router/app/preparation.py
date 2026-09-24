"""Exact-token, all-page preflight before any model load/forward."""
import time

from app import data

MAX_TOKENS = 8192
MAX_OBJECTIVE_TOKENS = 3072
MIN_HEADROOM = 256


def prepare_pages(tokenizer, pages, objective):
    from semif_phase1.core import direct_messages
    objective_tokens = len(tokenizer.encode(objective, add_special_tokens=False))
    errors, all_counts = [], []
    if objective_tokens > MAX_OBJECTIVE_TOKENS:
        errors.append(f"Compiled routing specification has {objective_tokens} tokens; objective budget is {MAX_OBJECTIVE_TOKENS}. "
                      "Further routing-specification compaction is required; no requested fields were truncated or removed.")
    for page in pages:
        started = time.perf_counter()
        state = data.TEMPLATE.format(objective=objective, page=page["page"], text=page["extracted_text"])
        rows = [{"id": f"page-{page['page']}-{key}", "state": state, "question": question, "options": data.OPTIONS}
                for key, question in data.QUESTIONS.items()]
        prompts = {key: tokenizer.apply_chat_template(direct_messages(row), tokenize=False, add_generation_prompt=True,
                                                      enable_thinking=False) for key, row in zip(data.QUESTIONS, rows)}
        counts = {key: len(tokenizer.encode(prompt, add_special_tokens=False)) for key, prompt in prompts.items()}
        headroom = {key: MAX_TOKENS - count for key, count in counts.items()}
        page_tokens = len(tokenizer.encode(page["extracted_text"], add_special_tokens=False))
        page.update(classifier_input=state, classifier_rows=rows, classification_questions=data.QUESTIONS,
                    classification_options=data.OPTIONS, exact_prompts=prompts, exact_prompt_tokens=counts,
                    available_token_headroom=headroom, page_text_tokens=page_tokens, tokens=page_tokens,
                    routing_objective_tokens=objective_tokens, scores=None, raw_distributions=None,
                    classification_status="prepared", classification_error=None, needs_router_review=False,
                    classification_seconds=0, exception=None, fallback=None,
                    context_preparation_seconds=time.perf_counter() - started)
        all_counts.extend(counts.values())
        if min(headroom.values()) < MIN_HEADROOM:
            errors.append(f"Page {page['page']}: largest exact prompt is {max(counts.values())} tokens, "
                          f"leaving {min(headroom.values())} headroom; require {MIN_HEADROOM} within {MAX_TOKENS}. "
                          "Compact the routing specification or review the oversized page; no truncation was applied.")
    return {"routing_objective_tokens": objective_tokens, "objective_token_budget": MAX_OBJECTIVE_TOKENS,
            "max_prompt_tokens": MAX_TOKENS, "minimum_required_headroom": MIN_HEADROOM,
            "exact_prompt_tokens_min": min(all_counts, default=0), "exact_prompt_tokens_max": max(all_counts, default=0),
            "available_token_headroom_min": MAX_TOKENS - max(all_counts, default=0),
            "input_preparation_errors": errors}
