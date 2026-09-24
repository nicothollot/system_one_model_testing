"""Versioned application criteria; SemIf's renderer and probability math are unchanged."""
PROMPT_VERSION = "direct-options-v2"
CRITERIA_VERSION = "semantic-equivalence-v2"
QUESTIONS = {
    "overall_relevance": "Could this page materially help extract or verify at least one requested target? Answer YES when there is a concrete connection to a requested target: the target itself, a necessary definition, an important assumption, a calculation input, or evidence needed to verify it. The same general financial or legal topic alone is not sufficient.",
    "requested_data": 'Is at least one requested target value or fact directly available on this page? Equivalent accounting, financial, legal or business synonyms count. Check every requested target: a match to any one target is sufficient. Exact section names are not required. Answer NO only if all targets are absent: nearby totals, components, cash-flow measures, availability, bookings or different periods alone do not count.',
    "supporting_context": "Does this page contain context materially useful or necessary to correctly interpret, calculate, distinguish, or verify at least one requested target? Generic accounting commentary or background not specifically useful to a requested target should be NO.",
    "financial_table": "Does this page contain a financial, transaction, valuation, or structured data table specifically relevant to at least one requested target? A table being financial in nature alone is not sufficient.",
    "cross_reference_or_footnote": "Does this page contain a note, definition, cross-reference, footnote, citation, or explanatory disclosure that specifically affects interpretation or verification of at least one requested target? Generic footnotes or unrelated cross-references should be NO.",
}
_DESCRIPTIONS = {
    "overall_relevance": ("Yes. Concrete information on this page materially helps extract or verify a requested target.", "No. There is no concrete material connection to a requested target; general topic similarity is insufficient."),
    "requested_data": ('Yes. At least one requested value or fact can be extracted from this page, including under an equivalent synonym and even alongside other metrics or fiscal periods.', 'No. None of the requested values or facts can be extracted; any information is merely related, uses a different accounting concept or period, or is generic context.'),
    "supporting_context": ("Yes. The page provides context materially useful to interpret, calculate, distinguish, or verify a specific requested target.", "No. Any commentary or background is generic or unrelated to interpreting, calculating, distinguishing, or verifying a requested target."),
    "financial_table": ("Yes. A structured table on this page contains data specifically relevant to a requested target.", "No. There is no table specifically relevant to a requested target; an unrelated financial table does not count."),
    "cross_reference_or_footnote": ("Yes. A note, definition, reference, or disclosure specifically affects interpretation or verification of a requested target.", "No. There is no note or reference with a specific effect on a requested target; generic or unrelated footnotes do not count."),
}
OPTIONS = {key: [{"id": "yes", "description": yes}, {"id": "no", "description": no}]
           for key, (yes, no) in _DESCRIPTIONS.items()}


def versions(run):
    """Missing application provenance means legacy v1, never current wording."""
    return {"prompt_version": run.get("prompt_version", "direct-options-v1"),
            "classifier_criteria_version": run.get("classifier_criteria_version", "legacy-v1")}
