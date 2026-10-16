from __future__ import annotations

import re


FAIL_TAG_ALIASES = {
    "notlessonoutcome": "outcome",
    "not_lesson_outcome": "outcome",
    "too_generic": "generic",
    "off_topic": "offtopic",
    "misleading_or_inaccurate": "inaccurate",
    "meaning_breaking_grammar": "grammar",
    "other_semantic_issue": "semantic",
    "not_glossary_concept": "glossary",
    "unclear_definition": "unclear",
    "weak_relevance": "relevance",
    "unclear_resource_value": "unclear",
    "trivia_or_recall_only": "trivia",
    "weak_module_coverage": "coverage",
    "acts_like_quiz": "quizlike",
    "weak_reflection_value": "reflection",
    "unclear_decision_point": "unclear",
    "weak_context": "context",
    "insufficient_detail": "detail",
    "missing_expected_component": "missing",
    "word_count": "wordcount",
    "blob": "photo",
    "blob_storage": "photo",
    "context_accurate_ai_review": "semantic",
}

FAIL_TAG_PRIORITY = [
    "missing",
    "photo",
    "duplicate",
    "grammar",
    "inaccurate",
    "offtopic",
    "semantic",
    "wordcount",
    "unclear",
    "glossary",
    "relevance",
    "coverage",
    "trivia",
    "quizlike",
    "reflection",
    "context",
    "detail",
    "generic",
    "outcome",
    "structure",
]

FAIL_TAG_COLORS = {
    "missing": "F4CCCC",
    "photo": "EA9999",
    "duplicate": "D9D2E9",
    "grammar": "FCE5CD",
    "inaccurate": "E06666",
    "offtopic": "F9CB9C",
    "semantic": "CFE2F3",
    "wordcount": "FFF2CC",
    "unclear": "FCE5CD",
    "glossary": "D9EAD3",
    "relevance": "D0E0E3",
    "coverage": "C9DAF8",
    "trivia": "C9DAF8",
    "quizlike": "D9D2E9",
    "reflection": "D9EAD3",
    "context": "D0E0E3",
    "detail": "EADCF8",
    "generic": "D9EAD3",
    "outcome": "D9EAD3",
    "structure": "EADCF8",
}


def normalize_fail_tag(value: object, *, default: str = "semantic") -> str:
    raw = str(value or "").strip().lower()
    if not raw or raw == "none":
        raw = default
    raw = raw.replace("-", "_").replace(" ", "_")
    raw = FAIL_TAG_ALIASES.get(raw, raw)
    compact = re.sub(r"[^a-z]", "", raw)
    if not compact:
        compact = default
    compact = FAIL_TAG_ALIASES.get(compact, compact)
    if compact not in FAIL_TAG_COLORS:
        return default if default in FAIL_TAG_COLORS else "semantic"
    return compact


def fail_tag_for_criterion(criterion: object) -> str:
    normalized = str(criterion or "").lower()
    if "word count" in normalized:
        return "wordcount"
    if "duplicate" in normalized or "unique" in normalized:
        return "duplicate"
    if "blob" in normalized:
        return "photo"
    if "llm" in normalized or "semantic" in normalized:
        return "semantic"
    if normalized.startswith("has ") or "missing expected" in normalized or "present" in normalized:
        return "missing"
    return "structure"


def choose_fail_tag(existing: object, candidate: object) -> str:
    current = normalize_fail_tag(existing, default="structure") if existing else ""
    next_tag = normalize_fail_tag(candidate, default="structure")
    if not current:
        return next_tag
    current_priority = FAIL_TAG_PRIORITY.index(current) if current in FAIL_TAG_PRIORITY else len(FAIL_TAG_PRIORITY)
    next_priority = FAIL_TAG_PRIORITY.index(next_tag) if next_tag in FAIL_TAG_PRIORITY else len(FAIL_TAG_PRIORITY)
    return next_tag if next_priority < current_priority else current
