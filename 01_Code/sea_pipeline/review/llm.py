from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from sea_pipeline.shared.clients import build_azure_openai_client
from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.io_json import load_json, save_json

from .controls import int_control, load_review_controls
from .extract import clean_display_text
from .models import LessonReviewInput, ReviewOutput
from .tags import normalize_fail_tag


PROMPT_VERSION = "academy-review-v10-critical-context-isolation"
LLM_COMPONENTS = {
    "takeaways": (
        "Evaluate each takeaway only for semantic quality: it should be a meaningful, lesson-aligned result or insight "
        "from the lesson, not a vague slogan or unrelated claim."
    ),
    "concepts": (
        "Evaluate each concept only for semantic quality: it should be a clear glossary-style concept used or strongly "
        "implied by the lesson, with a definition that is materially correct."
    ),
    "resources": (
        "Evaluate each resource only for semantic fit: based on title and URL text, it should plausibly support or extend "
        "the lesson topic. Do not require browsing the URL."
    ),
    "quiz": (
        "Evaluate each quiz question only for content quality: it should test module-level understanding or context, not "
        "only a trivial wording recall. Straightforward factual checks are acceptable if they support core module concepts."
    ),
    "poll": (
        "Evaluate each poll only for semantic quality: it should ask a meaningful learner reflection, judgment, or decision "
        "connected to the lesson, not function merely as a graded quiz."
    ),
    "case_study": (
        "Evaluate each case study only for semantic fit: it should be relevant to the surrounding lesson topic and have enough "
        "context to be useful."
    ),
}
LLM_GENERAL_GUIDANCE = (
    "Do not fail items for word count, missing fields, formatting, duplicate detection, broken image/blob links, or schema issues; "
    "those are checked separately by deterministic rules. Fail only when the item is materially off-topic, misleading, too generic "
    "to be useful, or semantically weak for the stated academy purpose. If an item is imperfect but usable and aligned, pass it and "
    "put the improvement in notes."
)
LLM_CRITICAL_GUIDANCE = (
    "Critical review mode: fail only severe issues that must be resolved for the item to make sense or avoid serious content problems. "
    "Examples: complete mismatch with the lesson or module, a claim that is materially misleading or inaccurate, nonsensical wording, "
    "or grammar/wording errors that change meaning or make the item hard to understand. Do not fail mild style issues, ordinary wording "
    "improvements, verbosity, weak-but-usable alignment, generic phrasing, minor grammar, word count, missing fields, duplicates, "
    "image/blob links, or schema issues. Do not fail because an excerpted lesson-context section appears cut off; excerpts are only "
    "supporting context and may be truncated."
)
LLM_DETAIL_COMPONENTS = {
    "takeaways": ("takeaway", "takeaways"),
    "concepts": ("concept", "concepts"),
    "resources": ("resource", "resources"),
    "quiz": ("quiz_question", "quiz"),
    "poll": ("poll",),
    "case_study": ("case_study",),
}


def _clean_llm_text(value: Any) -> str:
    text = clean_display_text(value)
    return re.sub(r"^(?:[-–—•]\s+|\d+[.)]\s+)", "", text).strip()


def _takeaway_text(item: dict[str, Any]) -> str:
    title = _clean_llm_text(item.get("title"))
    description = _clean_llm_text(item.get("description"))
    if title and description:
        if description.lower().startswith(title.lower()):
            return description
        return f"{title} {description}".strip()
    return next(
        (
            _clean_llm_text(item.get(key))
            for key in ("text", "body", "takeaway", "title", "description")
            if _clean_llm_text(item.get(key))
        ),
        "",
    )


def _collect_structured_text(value: Any, output: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"src", "href", "caption", "id", "pollId"}:
                continue
            if key in {"title", "subtitle", "intro", "body", "description", "text", "prompt", "value"} and isinstance(nested, str):
                text = _clean_llm_text(nested)
                if text:
                    output.append(text)
            else:
                _collect_structured_text(nested, output)
    elif isinstance(value, list):
        for item in value:
            _collect_structured_text(item, output)


def _truncate_for_context(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rstrip()
    sentence_boundary = max(clipped.rfind(". "), clipped.rfind("? "), clipped.rfind("! "))
    if sentence_boundary > max_chars * 0.6:
        return clipped[: sentence_boundary + 1].strip()
    word_boundary = clipped.rfind(" ")
    if word_boundary > max_chars * 0.8:
        return clipped[:word_boundary].strip()
    return clipped


def _lesson_content_sections(lesson: LessonReviewInput, max_chars: int) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    used_chars = 0
    for segment in lesson.data.get("segments", []):
        template_id = str(segment.get("template_id", ""))
        if template_id == "labels":
            continue
        pieces: list[str] = []
        _collect_structured_text(segment.get("content", {}), pieces)
        text = " ".join(pieces).strip()
        if not text:
            continue
        remaining = max_chars - used_chars
        if remaining <= 0:
            break
        excerpt = _truncate_for_context(text, remaining)
        sections.append({"template_id": template_id, "text": excerpt, "truncated": len(text) > len(excerpt)})
        used_chars += len(excerpt)
    return sections


def _feedback_body(messages: Any, key: str) -> str:
    if not isinstance(messages, dict):
        return ""
    value = messages.get(key)
    if isinstance(value, dict):
        return _clean_llm_text(value.get("body"))
    return _clean_llm_text(value)


LLM_FAIL_TAGS = {
    "takeaways": [
        "none",
        "outcome",
        "generic",
        "offtopic",
        "inaccurate",
        "grammar",
        "semantic",
    ],
    "concepts": [
        "none",
        "glossary",
        "unclear",
        "offtopic",
        "inaccurate",
        "grammar",
        "semantic",
    ],
    "resources": [
        "none",
        "relevance",
        "offtopic",
        "unclear",
        "inaccurate",
        "grammar",
        "semantic",
    ],
    "quiz": [
        "none",
        "trivia",
        "coverage",
        "offtopic",
        "inaccurate",
        "grammar",
        "semantic",
    ],
    "poll": [
        "none",
        "quizlike",
        "reflection",
        "offtopic",
        "unclear",
        "grammar",
        "semantic",
    ],
    "case_study": [
        "none",
        "context",
        "offtopic",
        "detail",
        "inaccurate",
        "grammar",
        "semantic",
    ],
}


def _load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    loaded = load_json(cache_path)
    return loaded if isinstance(loaded, dict) else {}


def _cache_key(
    lesson: LessonReviewInput,
    component: str,
    payload: Any,
    controls: dict[str, Any],
    review_context: str,
    review_mode: str = "full",
) -> str:
    raw = json.dumps(
        {
            "prompt_version": PROMPT_VERSION,
            "lesson_id": lesson.meta.lesson_id,
            "component": component,
            "review_mode": review_mode,
            "payload": payload,
            "review_context": review_context,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _component_payload(lesson: LessonReviewInput, component: str) -> Any:
    if component == "takeaways":
        payload = []
        for index, item in enumerate(lesson.takeaways, start=1):
            payload.append(
                {
                    "index": index,
                    "takeaway_text": _takeaway_text(item),
                }
            )
        return payload
    if component == "concepts":
        return [
            {
                "index": index,
                "concept": _clean_llm_text(item.get("title")),
                "definition": _clean_llm_text(item.get("body")),
            }
            for index, item in enumerate(lesson.concepts, start=1)
        ]
    if component == "resources":
        return [
            {
                "index": index,
                "resource_title": _clean_llm_text(item.get("text")),
                "resource_description": _clean_llm_text(item.get("description") or item.get("body")),
                "resource_url": str(item.get("href") or "").strip(),
            }
            for index, item in enumerate(lesson.resources, start=1)
        ]
    if component == "quiz":
        return [
            {
                "index": index,
                "prompt": _clean_llm_text(item.get("prompt")),
                "options": [_clean_llm_text(option.get("value")) for option in item.get("options", []) if isinstance(option, dict)],
                "solution": item.get("solution"),
                "correct_feedback": _feedback_body(item.get("messages"), "correct"),
                "wrong_feedback": _feedback_body(item.get("messages"), "wrong"),
            }
            for index, item in enumerate(lesson.quiz_questions, start=1)
        ]
    if component == "poll":
        return [
            {
                "index": index,
                "question": _clean_llm_text(item.get("title")),
                "options": [_clean_llm_text(option.get("value")) for option in item.get("options", []) if isinstance(option, dict)],
            }
            for index, item in enumerate(lesson.polls, start=1)
        ]
    if component == "case_study":
        return [
            {
                "index": index,
                "title": _clean_llm_text(item.get("title")),
                "subtitle": _clean_llm_text(item.get("subtitle")),
                "intro": _clean_llm_text(item.get("intro")),
                "body_excerpt": _clean_llm_text(item.get("_body_text"))[:1000],
            }
            for index, item in enumerate(lesson.case_studies, start=1)
        ]
    return {}


def _component_item_count(lesson: LessonReviewInput, component: str) -> int:
    if component == "takeaways":
        return len(lesson.takeaways)
    if component == "concepts":
        return len(lesson.concepts)
    if component == "resources":
        return len(lesson.resources)
    if component == "quiz":
        return len(lesson.quiz_questions)
    if component == "poll":
        return len(lesson.polls)
    if component == "case_study":
        return len(lesson.case_studies)
    return 0


def _component_item_value(lesson: LessonReviewInput, component: str, index: int) -> str:
    zero_index = index - 1
    if component == "takeaways" and 0 <= zero_index < len(lesson.takeaways):
        return _takeaway_text(lesson.takeaways[zero_index])
    if component == "concepts" and 0 <= zero_index < len(lesson.concepts):
        item = lesson.concepts[zero_index]
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        if title and body:
            return f"Concept: {title}\nDefinition: {body}"
        return title or body
    if component == "resources" and 0 <= zero_index < len(lesson.resources):
        item = lesson.resources[zero_index]
        return str(item.get("text") or item.get("href") or "")
    if component == "quiz" and 0 <= zero_index < len(lesson.quiz_questions):
        return str(lesson.quiz_questions[zero_index].get("prompt") or "")
    if component == "poll" and 0 <= zero_index < len(lesson.polls):
        return str(lesson.polls[zero_index].get("title") or "")
    if component == "case_study" and 0 <= zero_index < len(lesson.case_studies):
        return str(lesson.case_studies[zero_index].get("title") or lesson.case_studies[zero_index].get("intro") or "")
    return ""


def _item_results_by_index(result: dict[str, Any], item_count: int) -> dict[int, dict[str, Any]]:
    items = result.get("items", [])
    by_index = {int(item["index"]): item for item in items if isinstance(item, dict) and item.get("index")}
    if by_index:
        return by_index
    # Backward-compatible fallback for old cache entries or non-conforming responses.
    group_passed = bool(result.get("passed", True))
    group_notes = str(result.get("notes", "")).strip()
    return {
        index: {"index": index, "passed": group_passed, "notes": group_notes, "fail_tag": "none"}
        for index in range(1, item_count + 1)
    }


def _normalize_fail_tag(component: str, passed: bool, value: Any) -> str:
    if passed:
        return "none"
    allowed_tags = LLM_FAIL_TAGS.get(component, ["none", "semantic"])
    tag = normalize_fail_tag(value, default="semantic")
    if tag in allowed_tags and tag != "none":
        return tag
    return "semantic"


def _parse_llm_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"passed": False, "notes": f"LLM returned non-JSON response: {raw[:500]}"}
    if not isinstance(parsed, dict):
        return {"passed": False, "notes": "LLM returned a non-object JSON response."}
    item_results = parsed.get("items") or parsed.get("item_results") or []
    if isinstance(item_results, list):
        normalized_items = []
        for item in item_results:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            normalized_items.append(
                {
                    "index": index,
                    "passed": bool(item.get("passed", True)),
                    "notes": str(item.get("notes", "")).strip(),
                    "fail_tag": "none" if bool(item.get("passed", True)) else normalize_fail_tag(item.get("fail_tag"), default="semantic"),
                    "suggested_refinement": str(
                        item.get("suggested_refinement") or item.get("suggested_fix") or ""
                    ).strip(),
                }
            )
    else:
        normalized_items = []
    return {
        "passed": all(item.get("passed", True) for item in normalized_items) if normalized_items else bool(parsed.get("passed", True)),
        "notes": str(parsed.get("notes", "")).strip(),
        "details": parsed.get("details", []),
        "items": normalized_items,
    }


def _module_contexts(lessons: list[LessonReviewInput], controls: dict[str, Any]) -> dict[str, str]:
    context_max_chars = int_control(controls, "llm", "lesson_context_max_chars")
    contexts: dict[str, list[str]] = {}
    for lesson in lessons:
        if lesson.meta.lesson_type == "module_quiz":
            continue
        if not lesson.lesson_text:
            continue
        contexts.setdefault(lesson.meta.module_id, []).append(
            f"{lesson.meta.lesson_id} {lesson.meta.lesson_title}\n{lesson.lesson_text}"
        )
    return {
        module_id: "\n\n".join(parts)[:context_max_chars]
        for module_id, parts in contexts.items()
    }


def _review_context_for_component(
    lesson: LessonReviewInput,
    component: str,
    module_context_by_id: dict[str, str],
    controls: dict[str, Any],
) -> str:
    context_max_chars = int_control(controls, "llm", "lesson_context_max_chars")
    if component == "quiz":
        return (module_context_by_id.get(lesson.meta.module_id) or lesson.lesson_text)[:context_max_chars]
    return lesson.lesson_text[:context_max_chars]


def _build_llm_review_request(
    lesson: LessonReviewInput,
    component: str,
    payload: Any,
    controls: dict[str, Any],
    review_context: str,
    review_mode: str = "full",
) -> dict[str, Any]:
    context_max_chars = int_control(controls, "llm", "lesson_context_max_chars")
    lesson_context = {
        "lesson_id": lesson.meta.lesson_id,
        "lesson_type": lesson.meta.lesson_type,
        "module_title": lesson.meta.module_title,
        "chapter_title": lesson.meta.chapter_title,
        "lesson_title": lesson.meta.lesson_title,
        "segment_templates": lesson.segment_templates,
        "content_excerpt": review_context[:context_max_chars],
        "content_sections": _lesson_content_sections(lesson, context_max_chars),
    }
    if component == "resources":
        lesson_context["content_excerpt"] = ""
        lesson_context["content_sections"] = []
        lesson_context["resource_review_context"] = (
            "Resource review uses module_title, chapter_title, lesson_title, resource_title, and resource_url only. "
            "Do not review grammar, truncation, or completeness of lesson-body excerpts in this component."
        )
    if review_mode == "critical":
        lesson_context["content_excerpt"] = ""
        lesson_context["content_sections"] = []
        lesson_context["critical_review_context"] = (
            "Critical mode uses explicit item fields plus module_title, chapter_title, and lesson_title. "
            "Detailed lesson-body excerpts are intentionally omitted to avoid failing a component for surrounding context."
        )
    guidance = LLM_CRITICAL_GUIDANCE if review_mode == "critical" else LLM_GENERAL_GUIDANCE
    criterion = (
        f"Critical-only review for {component}: flag only complete mismatch, materially wrong/misleading content, "
        "or grammar/wording problems that prevent the item from making sense."
        if review_mode == "critical"
        else LLM_COMPONENTS[component]
    )
    return {
        "lesson_id": lesson.meta.lesson_id,
        "lesson_type": lesson.meta.lesson_type,
        "module_title": lesson.meta.module_title,
        "chapter_title": lesson.meta.chapter_title,
        "lesson_title": lesson.meta.lesson_title,
        "review_date": "2026-06-02",
        "criterion": criterion,
        "review_mode": review_mode,
        "allowed_fail_tags": LLM_FAIL_TAGS[component],
        "general_guidance": guidance,
        "review_instructions": (
            "Review each item independently against the criterion and lesson context. "
            "The item fields are authoritative; do not infer a different item structure from line breaks, bullets, "
            "numbering, HTML tags, em dashes, hyphen separators, table formatting, or JSON formatting. "
            "Use the deterministic checks only as background; do not fail for missing fields or word counts here. "
            "For takeaways, judge only the takeaway_text field; do not infer incompleteness from the absence of a separate "
            "title or description. If title and description are both present for other component types, judge their combined "
            "meaning rather than either fragment alone. "
            "If formatting makes the content excerpt unclear, rely on lesson_title, module_title, chapter_title, "
            "content_sections, and the explicit item fields. "
            "Content excerpts may be truncated and are not the component under review; never fail a component because a "
            "context excerpt ends abruptly or appears incomplete. "
            "In critical mode, detailed lesson-body context is intentionally omitted; judge severe issues from the explicit "
            "item fields and the lesson/module/chapter titles only. "
            "For resources, judge only whether the resource title and URL are plausibly relevant to the lesson; do not "
            "fail publication years or title dates unless the item itself contains an explicit contradiction. The review "
            "date is 2026-06-02, so 2025 titles are not future-dated. Do not fail a resource because the lesson body, "
            "content excerpt, or surrounding context has grammar issues; those are not resource quality issues. "
            "In critical mode, do not fail an item for being wordy, broad, redundant, or stylistically improvable if the "
            "meaning is understandable and aligned. "
            "For any failed item, explain the exact semantic problem and provide a targeted refinement that says what "
            "to change, add, remove, or refocus. For concepts, judge the concept name and definition together against "
            "the lesson title and content excerpt. For every passing item, return fail_tag='none'. For every failing "
            "item, choose exactly one fail_tag from allowed_fail_tags. Return exactly one result per input item, using "
            "the same index values provided in items. In critical mode, pass anything that is merely "
            "weak, generic, stylistically imperfect, or mildly improvable but still understandable and not materially mismatched."
        ),
        "response_schema": {
            "passed": "boolean: true only if all reviewed items pass semantic review",
            "notes": "short overall note",
            "items": [
                {
                    "index": 1,
                    "passed": True,
                    "fail_tag": "one of allowed_fail_tags; use none only when passed is true",
                    "notes": "short diagnosis tied to this item",
                    "suggested_refinement": "specific improvement instruction; blank if no refinement is needed",
                }
            ],
        },
        "lesson_context": lesson_context,
        "items": payload,
    }


def _call_llm(
    config: PipelineConfig,
    lesson: LessonReviewInput,
    component: str,
    payload: Any,
    controls: dict[str, Any],
    review_context: str,
    review_mode: str = "full",
) -> dict[str, Any]:
    if not config.env.azure_openai_deployment:
        raise ValueError("AZURE_OPENAI_DEPLOYMENT is required for LLM review.")
    client = build_azure_openai_client(config.env)
    system = (
        "You are reviewing Sustainable Energy Academy lesson JSON for semantic content quality. "
        "Return only JSON with keys: passed (boolean), notes (string), and items (array). "
        "Each items entry must have: index (integer), passed (boolean), fail_tag (string), "
        "notes (short diagnosis), and suggested_refinement (targeted improvement instruction). "
        "Use fail_tag='none' for passing items and exactly one allowed fail tag for failing items. "
        "If review_mode is critical, fail only severe blocking issues that must be fixed. "
        "Be fair and precise; do not over-reject usable content."
    )
    user = _build_llm_review_request(lesson, component, payload, controls, review_context, review_mode=review_mode)
    request = {
        "model": config.env.azure_openai_deployment,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "temperature": int_control(controls, "llm", "temperature"),
        "max_tokens": int_control(controls, "llm", "max_tokens"),
    }
    try:
        response = client.chat.completions.create(**request, response_format={"type": "json_object"})
    except Exception as exc:  # noqa: BLE001 - retry only for deployments without JSON mode.
        message = str(exc).lower()
        if "response_format" not in message and "json_object" not in message:
            raise
        response = client.chat.completions.create(**request)
    return _parse_llm_json(response.choices[0].message.content or "")


def apply_llm_review(
    output: ReviewOutput,
    lessons: list[LessonReviewInput],
    config: PipelineConfig,
    cache_path: str | Path,
    controls: dict[str, Any] | None = None,
    components: set[str] | None = None,
    review_mode: str = "full",
    log: Callable[[str], None] | None = None,
) -> ReviewOutput:
    review_mode = review_mode.strip().lower() if isinstance(review_mode, str) else "full"
    if review_mode not in {"full", "critical"}:
        review_mode = "full"
    controls = controls or load_review_controls()
    cache_file = Path(cache_path)
    cache = _load_cache(cache_file)
    module_context_by_id = _module_contexts(lessons, controls)
    total_lessons = len(lessons)
    for lesson_index, lesson in enumerate(lessons, start=1):
        if log:
            log(f"[LLM] Review {lesson_index}/{total_lessons}: {lesson.meta.lesson_id}")
        lesson_notes: list[str] = []
        lesson_failed = False
        for component in LLM_COMPONENTS:
            if components is not None and component not in components:
                continue
            payload = _component_payload(lesson, component)
            if not payload:
                continue
            review_context = _review_context_for_component(lesson, component, module_context_by_id, controls)
            key = _cache_key(lesson, component, payload, controls, review_context, review_mode=review_mode)
            if key in cache:
                result = cache[key]
                output.cache_hits += 1
                if log:
                    log(f"  [cache] {component}: hit")
            else:
                output.cache_misses += 1
                if log:
                    log(f"  [openai] {component}: {review_mode} review")
                try:
                    result = _call_llm(config, lesson, component, payload, controls, review_context, review_mode=review_mode)
                except Exception as exc:  # noqa: BLE001 - this is notebook-facing audit output.
                    result = {"passed": False, "notes": f"LLM review error: {type(exc).__name__}: {exc}", "details": []}
                    output.llm_errors += 1
                cache[key] = result
            item_count = _component_item_count(lesson, component)
            item_results = _item_results_by_index(result, item_count)
            passed = all(bool(item_results.get(index, {"passed": True}).get("passed", True)) for index in range(1, item_count + 1))
            notes = str(result.get("notes", "")).strip()
            if not passed:
                lesson_failed = True
                lesson_notes.append(f"{component}: {notes}")
            for item_index in range(1, item_count + 1):
                item_result = item_results.get(item_index, {"passed": True, "notes": ""})
                item_passed = bool(item_result.get("passed", True))
                item_notes = str(item_result.get("notes") or notes).strip()
                fail_tag = _normalize_fail_tag(component, item_passed, item_result.get("fail_tag"))
                item_suggestion = str(item_result.get("suggested_refinement") or "").strip()
                if not item_suggestion and not item_passed:
                    item_suggestion = "Revise content based on the semantic review note."
                output.component_rows.append(
                    {
                        "lesson_id": lesson.meta.lesson_id,
                        "module_id": lesson.meta.module_id,
                        "chapter_id": lesson.meta.chapter_id,
                        "lesson_type": lesson.meta.lesson_type,
                        "component": LLM_DETAIL_COMPONENTS[component][0],
                        "component_index": item_index,
                        "criterion": "llm semantic review",
                        "status": "pass" if item_passed else "fail",
                        "fail_tag": fail_tag,
                        "notes": item_notes,
                        "suggested_fix": item_suggestion if not item_passed else "",
                        "value": _component_item_value(lesson, component, item_index),
                        "source_json": str(lesson.meta.path),
                    }
                )
        for row in output.lesson_rows:
            if row["lesson_id"] != lesson.meta.lesson_id:
                continue
            row["llm_status"] = "fail" if lesson_failed else "pass"
            row["llm_notes"] = " | ".join(lesson_notes)
            if lesson_failed:
                row["overall_status"] = "fail"
                row["overall_notes"] = (row.get("overall_notes") or "") + (" | " if row.get("overall_notes") else "") + "LLM semantic review failed."
    save_json(cache, cache_file)
    if log:
        log(f"[Review] Cache written: {cache_file}")
    output.cache_path = cache_file
    return output
