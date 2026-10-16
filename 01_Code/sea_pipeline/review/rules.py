from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .blob_checks import ResourceBlobChecker
from .controls import int_control, load_review_controls
from .extract import clean_display_text, normalize_for_duplicate, word_count
from .models import MODULE_QUIZ, NORMAL_LESSON, LessonReviewInput, ReviewOutput


COMPONENTS = ("takeaways", "concepts", "resources", "quiz", "poll", "case_study")
DETAIL_COMPONENTS_BY_COMPONENT = {
    "takeaways": {"takeaway", "takeaways"},
    "concepts": {"concept", "concepts"},
    "resources": {"resource", "resources"},
    "quiz": {"quiz_question", "quiz"},
    "poll": {"poll"},
    "case_study": {"case_study"},
}


def _concept_value(item: dict[str, Any]) -> str:
    title = clean_display_text(item.get("title", ""))
    body = clean_display_text(item.get("body", ""))
    if title and body:
        return f"Concept: {title}\nDefinition: {body}"
    return title or body


def _takeaway_value(item: dict[str, Any]) -> str:
    title = clean_display_text(item.get("title", ""))
    description = clean_display_text(item.get("description", ""))
    if title and description:
        if description.lower().startswith(title.lower()):
            return description
        return f"{title} {description}".strip()
    for key in ("text", "body", "takeaway", "title", "description"):
        text = clean_display_text(item.get(key, ""))
        if text:
            return text
    return ""


def _word_count_range_detail(label: str, values: list[tuple[str, int]], minimum: int, maximum: int) -> str:
    details = []
    for text, count in values:
        if _word_count_in_range(count, minimum, maximum):
            continue
        display_text = text or "[blank]"
        if count < minimum:
            details.append(f"{label} '{display_text}' has {count} words; minimum is {minimum}.")
        else:
            details.append(f"Reduce {label.lower()} '{display_text}' to {maximum} words maximum, currently at {count}.")
    return " ".join(details)


def _max_with_buffer(maximum: int) -> int:
    return math.ceil(maximum * 1.1)


def _word_count_in_range(count: int, minimum: int, maximum: int) -> bool:
    return minimum <= count <= _max_with_buffer(maximum)


def _word_count_detail(label: str, count: int, minimum: int, maximum: int) -> str:
    if count < minimum:
        return f"{label} has {count} words; minimum is {minimum}."
    if count > _max_with_buffer(maximum):
        return f"Reduce {label.lower()} to {maximum} words maximum, currently at {count}."
    return ""


def _word_count_range_pass(values: list[tuple[str, int]], minimum: int, maximum: int) -> bool:
    return bool(values) and all(_word_count_in_range(count, minimum, maximum) for _, count in values)


def _pass(value: bool) -> str:
    return "pass" if value else "fail"


def _add_component_row(
    output: ReviewOutput,
    lesson: LessonReviewInput,
    component: str,
    component_index: int,
    criterion: str,
    passed: bool,
    notes: str = "",
    suggested_fix: str = "",
    value: str = "",
) -> None:
    output.component_rows.append(
        {
            "lesson_id": lesson.meta.lesson_id,
            "module_id": lesson.meta.module_id,
            "chapter_id": lesson.meta.chapter_id,
            "lesson_type": lesson.meta.lesson_type,
            "component": component,
            "component_index": component_index,
            "criterion": criterion,
            "status": _pass(passed),
            "notes": notes,
            "suggested_fix": suggested_fix,
            "value": clean_display_text(value)[:2000],
            "source_json": str(lesson.meta.path),
        }
    )


def _add_gap(
    output: ReviewOutput,
    lesson: LessonReviewInput,
    component: str,
    expected: str,
    actual: str,
    required: bool,
    notes: str,
) -> None:
    output.gap_rows.append(
        {
            "lesson_id": lesson.meta.lesson_id,
            "module_id": lesson.meta.module_id,
            "chapter_id": lesson.meta.chapter_id,
            "lesson_type": lesson.meta.lesson_type,
            "component": component,
            "expected": expected,
            "actual": actual,
            "required": required,
            "notes": notes,
            "source_json": str(lesson.meta.path),
        }
    )


def _duplicate_occurrence_notes(items: list[dict[str, Any]], keys: list[tuple[str, str]]) -> dict[int, str]:
    seen: dict[tuple[str, str], int] = {}
    duplicate_notes: dict[int, list[str]] = defaultdict(list)
    for item in items:
        idx = int(item.get("_component_index", 0))
        for key, label in keys:
            value = normalize_for_duplicate(item.get(key, ""))
            if not value:
                continue
            seen_key = (key, value)
            first_idx = seen.get(seen_key)
            if first_idx is not None:
                duplicate_notes[idx].append(f"Duplicate {label}; first appears as item {first_idx}.")
            else:
                seen[seen_key] = idx
    return {idx: " ".join(notes) for idx, notes in duplicate_notes.items()}


def _row_status(component_notes: list[str]) -> tuple[str, str]:
    if component_notes:
        return "fail", " | ".join(component_notes)
    return "pass", ""


def _review_takeaways(output: ReviewOutput, lesson: LessonReviewInput, controls: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    count = len(lesson.takeaways)
    expected_takeaways = int_control(controls, "normal_lesson", "expected_takeaways")
    if lesson.meta.lesson_type == NORMAL_LESSON and count != expected_takeaways:
        notes.append(f"Expected {expected_takeaways} takeaways, found {count}.")
        _add_gap(output, lesson, "takeaways", str(expected_takeaways), str(count), True, f"Normal lessons should end with {expected_takeaways} takeaways.")
    if count and "key_takeaways" in lesson.segment_templates:
        index = lesson.segment_templates.index("key_takeaways")
        near_end_window = int_control(controls, "takeaways", "near_end_segment_window")
        if index < max(0, len(lesson.segment_templates) - near_end_window):
            notes.append("Key takeaways are not near the end of the lesson.")
    takeaway_values = [normalize_for_duplicate(_takeaway_value(item)) for item in lesson.takeaways if _takeaway_value(item)]
    if len(takeaway_values) != len(set(takeaway_values)):
        notes.append("Duplicate takeaway text within lesson.")
    for item in lesson.takeaways:
        idx = int(item.get("_component_index", 0))
        takeaway_text = _takeaway_value(item)
        text_words = word_count(takeaway_text)
        text_min = int_control(controls, "takeaways", "text_min_words")
        text_max = int_control(controls, "takeaways", "text_max_words")
        checks = [
            ("has takeaway text", bool(takeaway_text), "Add a clear result-oriented takeaway."),
            (
                f"takeaway text word count {text_min}-{text_max}",
                _word_count_in_range(text_words, text_min, text_max),
                _word_count_detail("Takeaway", text_words, text_min, text_max),
            ),
        ]
        for criterion, passed, detail in checks:
            if not passed:
                notes.append(f"Takeaway {idx}: {detail}")
            _add_component_row(output, lesson, "takeaway", idx, criterion, passed, detail if not passed else "", value=takeaway_text)
    return notes


def _review_concepts(output: ReviewOutput, lesson: LessonReviewInput, controls: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    count = len(lesson.concepts)
    expected_concepts = int_control(controls, "normal_lesson", "expected_concepts")
    if lesson.meta.lesson_type == NORMAL_LESSON and count != expected_concepts:
        notes.append(f"Expected {expected_concepts} key concepts, found {count}.")
        _add_gap(output, lesson, "concepts", str(expected_concepts), str(count), True, f"Normal lessons should have {expected_concepts} glossary-style concepts.")
    duplicate_notes = _duplicate_occurrence_notes(lesson.concepts, [("title", "concept title")])
    for item in lesson.concepts:
        idx = int(item.get("_component_index", 0))
        title_words = word_count(item.get("title", ""))
        body_words = word_count(item.get("body", ""))
        title = clean_display_text(item.get("title", ""))
        body = clean_display_text(item.get("body", ""))
        title_min = int_control(controls, "concepts", "title_min_words")
        title_max = int_control(controls, "concepts", "title_max_words")
        definition_min = int_control(controls, "concepts", "definition_min_words")
        definition_max = int_control(controls, "concepts", "definition_max_words")
        checks = [
            ("has concept title", bool(title), "Add a glossary-style concept name."),
            ("has definition body", bool(body), "Add a clear definition."),
            (
                f"title word count {title_min}-{title_max}",
                _word_count_in_range(title_words, title_min, title_max),
                _word_count_detail("Concept title", title_words, title_min, title_max),
            ),
            (
                f"definition word count {definition_min}-{definition_max}",
                _word_count_in_range(body_words, definition_min, definition_max),
                _word_count_detail("Concept definition", body_words, definition_min, definition_max),
            ),
        ]
        for criterion, passed, detail in checks:
            if not passed:
                notes.append(f"Concept {idx}: {detail}")
            _add_component_row(output, lesson, "concept", idx, criterion, passed, detail if not passed else "", value=_concept_value(item))
        duplicate_detail = duplicate_notes.get(idx, "")
        if duplicate_detail:
            notes.append(f"Concept {idx}: {duplicate_detail}")
        _add_component_row(
            output,
            lesson,
            "concept",
            idx,
            "duplicate concept title",
            not duplicate_detail,
            duplicate_detail,
            "Rewrite or confirm the repeated concept is intentional." if duplicate_detail else "",
            _concept_value(item),
        )
    return notes


def _review_resources(output: ReviewOutput, lesson: LessonReviewInput, controls: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    count = len(lesson.resources)
    expected_resources = int_control(controls, "normal_lesson", "expected_resources")
    if lesson.meta.lesson_type == NORMAL_LESSON and count != expected_resources:
        notes.append(f"Expected {expected_resources} resources, found {count}.")
        _add_gap(output, lesson, "resources", str(expected_resources), str(count), True, f"Normal lessons should have {expected_resources} key resources.")
    duplicate_notes = _duplicate_occurrence_notes(lesson.resources, [("text", "resource title"), ("href", "resource href")])
    for item in lesson.resources:
        idx = int(item.get("_component_index", 0))
        text = clean_display_text(item.get("text", ""))
        href = clean_display_text(item.get("href", ""))
        image = item.get("image") if isinstance(item.get("image"), dict) else {}
        text_words = word_count(text)
        text_min = int_control(controls, "resources", "text_min_words")
        text_max = int_control(controls, "resources", "text_max_words")
        checks = [
            ("has resource text", bool(text), "Add a resource title."),
            (
                f"text word count {text_min}-{text_max}",
                _word_count_in_range(text_words, text_min, text_max),
                _word_count_detail("Resource text", text_words, text_min, text_max),
            ),
            ("has URL href", href.startswith(("http://", "https://")), "Add a valid http(s) href."),
            ("has image src", bool(clean_display_text(image.get("src", ""))), "Add a resource image src."),
        ]
        for criterion, passed, detail in checks:
            if not passed:
                notes.append(f"Resource {idx}: {detail}")
            _add_component_row(output, lesson, "resource", idx, criterion, passed, detail if not passed else "", value=text)
        duplicate_detail = duplicate_notes.get(idx, "")
        if duplicate_detail:
            notes.append(f"Resource {idx}: {duplicate_detail}")
        _add_component_row(
            output,
            lesson,
            "resource",
            idx,
            "duplicate resource title or href",
            not duplicate_detail,
            duplicate_detail,
            "Replace or confirm the repeated resource is intentional." if duplicate_detail else "",
            text,
        )
    return notes


def _review_resource_blobs(
    output: ReviewOutput,
    lesson: LessonReviewInput,
    resource_blob_checker: ResourceBlobChecker | None,
) -> list[str]:
    notes: list[str] = []
    if resource_blob_checker is None:
        return notes
    for item in lesson.resources:
        idx = int(item.get("_component_index", 0))
        text = clean_display_text(item.get("text", ""))
        image = item.get("image") if isinstance(item.get("image"), dict) else {}
        src = clean_display_text(image.get("src", ""))
        if not src:
            continue
        result = resource_blob_checker(src)
        passed = result.exists
        photo_ref = result.blob_name or src
        photo_id = Path(str(photo_ref).split("?", 1)[0]).stem or str(photo_ref)
        detail_message = result.message or result.status
        if result.blob_name:
            detail_message = detail_message.replace(result.blob_name, photo_id)
        detail_message = detail_message.replace(src, photo_id)
        detail = f"Photo {photo_id}: {detail_message}" if detail_message else f"Photo {photo_id}"
        if not passed:
            notes.append(f"Resource {idx}: resource photo missing or unavailable ({detail}).")
        _add_component_row(
            output,
            lesson,
            "resource",
            idx,
            "resource image exists in blob storage",
            passed,
            detail if not passed else "",
            "Upload the missing resource image or correct the image src." if not passed else "",
            text,
        )
    return notes


def _review_quiz(output: ReviewOutput, lesson: LessonReviewInput, controls: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    count = len(lesson.quiz_questions)
    minimum_questions = int_control(controls, "quiz", "minimum_questions")
    preferred_questions = int_control(controls, "quiz", "preferred_questions")
    if lesson.meta.lesson_type == MODULE_QUIZ:
        if count < minimum_questions:
            notes.append(f"Quiz has {count} questions; minimum is {minimum_questions}.")
            _add_gap(output, lesson, "quiz", f"at least {minimum_questions} questions", str(count), True, "Add module-level quiz questions.")
        elif count != preferred_questions:
            notes.append(f"Quiz has {count} questions; {preferred_questions} is preferred.")
    if lesson.meta.lesson_type != MODULE_QUIZ and count:
        notes.append("Scored quiz appears outside a module quiz lesson.")
    prompts = [normalize_for_duplicate(q.get("prompt", "")) for q in lesson.quiz_questions]
    if len([p for p in prompts if p]) != len(set(p for p in prompts if p)):
        notes.append("Duplicate quiz prompts within quiz.")
    for question in lesson.quiz_questions:
        idx = int(question.get("_component_index", question.get("id", 0) or 0))
        prompt = clean_display_text(question.get("prompt", ""))
        options = question.get("options", []) if isinstance(question.get("options"), list) else []
        solution = question.get("solution", []) if isinstance(question.get("solution"), list) else []
        messages = question.get("messages", {}) if isinstance(question.get("messages"), dict) else {}
        option_values = [clean_display_text(option.get("value", "")) for option in options if isinstance(option, dict)]
        minimum_options = int_control(controls, "quiz", "minimum_options")
        prompt_min = int_control(controls, "quiz", "prompt_min_words")
        prompt_max = int_control(controls, "quiz", "prompt_max_words")
        option_min = int_control(controls, "quiz", "option_min_words")
        option_max = int_control(controls, "quiz", "option_max_words")
        prompt_words = word_count(prompt)
        option_counts = [(value, word_count(value)) for value in option_values]
        option_word_counts_pass = _word_count_range_pass(option_counts, option_min, option_max)
        checks = [
            ("has prompt", bool(prompt), "Add a question prompt."),
            (
                f"prompt word count {prompt_min}-{prompt_max}",
                _word_count_in_range(prompt_words, prompt_min, prompt_max),
                _word_count_detail("Quiz prompt", prompt_words, prompt_min, prompt_max),
            ),
            (f"has at least {minimum_options} options", len(option_values) >= minimum_options, f"Question has {len(option_values)} options."),
            (
                f"option word count {option_min}-{option_max}",
                option_word_counts_pass,
                _word_count_range_detail("Quiz option", option_counts, option_min, option_max),
            ),
            ("has solution", bool(solution), "Add solution option IDs."),
            ("has feedback", bool(messages.get("correct") and messages.get("wrong")), "Add correct and wrong feedback."),
            ("unique options", len(option_values) == len(set(option_values)), "Options contain duplicates."),
        ]
        for criterion, passed, detail in checks:
            if not passed:
                notes.append(f"Quiz question {idx}: {detail}")
            _add_component_row(output, lesson, "quiz_question", idx, criterion, passed, detail if not passed else "", value=prompt)
    return notes


def _review_polls(output: ReviewOutput, lesson: LessonReviewInput, expect_poll: bool, controls: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    count = len(lesson.polls)
    expected_polls = int_control(controls, "normal_lesson", "expected_polls")
    if lesson.meta.lesson_type == NORMAL_LESSON and expect_poll and count != expected_polls:
        notes.append(f"Expected {expected_polls} poll, found {count}.")
        _add_gap(output, lesson, "poll", str(expected_polls), str(count), True, f"Normal lessons should have {expected_polls} poll.")
    for poll in lesson.polls:
        idx = int(poll.get("_component_index", 0))
        title = clean_display_text(poll.get("title", ""))
        options = poll.get("options", []) if isinstance(poll.get("options"), list) else []
        option_values = [clean_display_text(option.get("value", "")) for option in options if isinstance(option, dict)]
        minimum_options = int_control(controls, "poll", "minimum_options")
        question_min = int_control(controls, "poll", "question_min_words")
        question_max = int_control(controls, "poll", "question_max_words")
        option_min = int_control(controls, "poll", "option_min_words")
        option_max = int_control(controls, "poll", "option_max_words")
        question_words = word_count(title)
        option_counts = [(value, word_count(value)) for value in option_values]
        option_word_counts_pass = _word_count_range_pass(option_counts, option_min, option_max)
        checks = [
            ("has title", bool(title), "Add a poll title/question."),
            (
                f"question word count {question_min}-{question_max}",
                _word_count_in_range(question_words, question_min, question_max),
                _word_count_detail("Poll question", question_words, question_min, question_max),
            ),
            (f"has at least {minimum_options} options", len(option_values) >= minimum_options, f"Poll has {len(option_values)} options."),
            (
                f"option word count {option_min}-{option_max}",
                option_word_counts_pass,
                _word_count_range_detail("Poll option", option_counts, option_min, option_max),
            ),
            ("unique options", len(option_values) == len(set(option_values)), "Poll options contain duplicates."),
            ("has labels", isinstance(poll.get("labels"), dict) and bool(poll.get("labels")), "Add poll labels."),
        ]
        for criterion, passed, detail in checks:
            if not passed:
                notes.append(f"Poll {idx}: {detail}")
            _add_component_row(output, lesson, "poll", idx, criterion, passed, detail if not passed else "", value=title)
    return notes


def _review_case_studies(output: ReviewOutput, lesson: LessonReviewInput, controls: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    titles = [normalize_for_duplicate(study.get("title", "")) for study in lesson.case_studies if normalize_for_duplicate(study.get("title", ""))]
    if len(titles) != len(set(titles)):
        notes.append("Duplicate case study title within lesson.")
    for study in lesson.case_studies:
        idx = int(study.get("_component_index", 0))
        title = clean_display_text(study.get("title", ""))
        subtitle = clean_display_text(study.get("subtitle", ""))
        subtitle_max = int_control(controls, "case_study", "subtitle_max_words")
        subtitle_words = word_count(subtitle)
        checks = [
            ("has title", bool(title), "Add a case study title."),
        ]
        if subtitle:
            checks.append(
                (
                    f"subtitle word count 0-{subtitle_max}",
                    _word_count_in_range(subtitle_words, 0, subtitle_max),
                    _word_count_detail("Case study subtitle", subtitle_words, 0, subtitle_max),
                )
            )
        for criterion, passed, detail in checks:
            if not passed:
                notes.append(f"Case study {idx}: {detail}")
            _add_component_row(output, lesson, "case_study", idx, criterion, passed, detail if not passed else "", value=title)
    return notes


def _apply_cross_lesson_duplicates(
    output: ReviewOutput,
    lessons: list[LessonReviewInput],
    *,
    components: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    seen: dict[str, dict[str, str]] = defaultdict(dict)
    duplicate_notes: dict[str, dict[str, str]] = defaultdict(dict)
    checks = [
        ("takeaways", "takeaway", "takeaways", "title"),
        ("concepts", "concept", "concepts", "title"),
        ("resources", "resource", "resources", "href"),
        ("polls", "poll", "poll", "title"),
        ("case_studies", "case_study", "case_study", "title"),
    ]
    for lesson in lessons:
        for attr, detail_component, row_component, key in checks:
            if components is not None and row_component not in components:
                continue
            for item in getattr(lesson, attr):
                raw_value = _takeaway_value(item) if attr == "takeaways" else item.get(key, "")
                key_label = "text" if attr == "takeaways" else key
                value = normalize_for_duplicate(raw_value)
                if not value:
                    continue
                first_lesson = seen[detail_component].get(value)
                if first_lesson and first_lesson != lesson.meta.lesson_id:
                    note = f"Duplicate {detail_component} {key_label} also appears in {first_lesson}."
                    duplicate_notes[lesson.meta.lesson_id][row_component] = note
                    _add_component_row(
                        output,
                        lesson,
                        detail_component,
                        int(item.get("_component_index", 0)),
                        "cross-lesson duplicate",
                        False,
                        note,
                        "Rewrite or confirm the repeated item is intentional.",
                        raw_value,
                    )
                else:
                    seen[detail_component][value] = lesson.meta.lesson_id
    return duplicate_notes


def _clear_component_output(output: ReviewOutput, component: str) -> None:
    detail_components = DETAIL_COMPONENTS_BY_COMPONENT[component]
    output.component_rows = [
        row for row in output.component_rows
        if row.get("component") not in detail_components
    ]
    output.gap_rows = [
        row for row in output.gap_rows
        if row.get("component") != component
    ]
    for lesson_notes in output.component_notes.values():
        lesson_notes.pop(component, None)


def _sync_lesson_rows(output: ReviewOutput, lessons: list[LessonReviewInput]) -> None:
    rows: list[dict[str, Any]] = []
    for lesson in lessons:
        row: dict[str, Any] = {
            "lesson_id": lesson.meta.lesson_id,
            "module_id": lesson.meta.module_id,
            "chapter_id": lesson.meta.chapter_id,
            "lesson_type": lesson.meta.lesson_type,
            "module_title": lesson.meta.module_title,
            "chapter_title": lesson.meta.chapter_title,
            "lesson_title": lesson.meta.lesson_title,
            "source_json": str(lesson.meta.path),
        }
        overall_failures: list[str] = []
        lesson_notes = output.component_notes.get(lesson.meta.lesson_id, {})
        for component in COMPONENTS:
            if component not in output.completed_components:
                row[f"{component}_status"] = "not_run"
                row[f"{component}_notes"] = ""
                continue
            status, notes = _row_status(lesson_notes.get(component, []))
            row[f"{component}_status"] = status
            row[f"{component}_notes"] = notes
            if status == "fail":
                overall_failures.append(component)
        row["duplicates_status"] = "fail" if any("Duplicate" in note for notes in lesson_notes.values() for note in notes) else "pass"
        row["duplicates_notes"] = " | ".join(
            note for notes in lesson_notes.values() for note in notes if "Duplicate" in note
        )
        row["gaps_status"] = "fail" if any(gap["lesson_id"] == lesson.meta.lesson_id for gap in output.gap_rows) else "pass"
        row["gaps_notes"] = " | ".join(gap["notes"] for gap in output.gap_rows if gap["lesson_id"] == lesson.meta.lesson_id)
        row["llm_status"] = "not_run"
        row["llm_notes"] = ""
        row["overall_status"] = "fail" if overall_failures or row["gaps_status"] == "fail" or row["duplicates_status"] == "fail" else "pass"
        row["overall_notes"] = "Failed components: " + ", ".join(overall_failures) if overall_failures else ""
        rows.append(row)
    output.lesson_rows = rows


def run_component_review(
    lessons: list[LessonReviewInput],
    component: str,
    *,
    output: ReviewOutput | None = None,
    expect_poll_for_normal_lessons: bool = False,
    controls: dict[str, Any] | None = None,
    resource_blob_checker: ResourceBlobChecker | None = None,
) -> ReviewOutput:
    if component not in COMPONENTS:
        raise KeyError(f"Unknown review component: {component}")
    controls = controls or load_review_controls()
    output = output or ReviewOutput()
    _clear_component_output(output, component)
    duplicate_notes = _apply_cross_lesson_duplicates(output, lessons, components={component})
    for lesson in lessons:
        if component == "takeaways":
            notes = _review_takeaways(output, lesson, controls)
        elif component == "concepts":
            notes = _review_concepts(output, lesson, controls)
        elif component == "resources":
            notes = [
                *_review_resources(output, lesson, controls),
                *_review_resource_blobs(output, lesson, resource_blob_checker),
            ]
        elif component == "quiz":
            notes = _review_quiz(output, lesson, controls)
        elif component == "poll":
            notes = _review_polls(output, lesson, expect_poll_for_normal_lessons, controls)
        elif component == "case_study":
            notes = _review_case_studies(output, lesson, controls)
        else:
            notes = []
        for duplicate_component, duplicate_note in duplicate_notes.get(lesson.meta.lesson_id, {}).items():
            if duplicate_component == component:
                notes.append(duplicate_note)
        output.component_notes.setdefault(lesson.meta.lesson_id, {})[component] = notes
    output.completed_components.add(component)
    _sync_lesson_rows(output, lessons)
    return output


def run_deterministic_review(
    lessons: list[LessonReviewInput],
    *,
    expect_poll_for_normal_lessons: bool = False,
    controls: dict[str, Any] | None = None,
    resource_blob_checker: ResourceBlobChecker | None = None,
) -> ReviewOutput:
    controls = controls or load_review_controls()
    output = ReviewOutput()
    for component in COMPONENTS:
        run_component_review(
            lessons,
            component,
            output=output,
            expect_poll_for_normal_lessons=expect_poll_for_normal_lessons,
            controls=controls,
            resource_blob_checker=resource_blob_checker,
        )
    return output
