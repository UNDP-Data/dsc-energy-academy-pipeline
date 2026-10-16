from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from sea_pipeline.shared.io_json import load_json

from .models import (
    CHAPTER_INTRO,
    CHAPTER_OUTRO,
    MODULE_INTRO,
    MODULE_OUTRO,
    MODULE_QUIZ,
    NORMAL_LESSON,
    LessonMeta,
    LessonReviewInput,
)


TEXT_KEYS = {"title", "subtitle", "intro", "body", "description", "text", "prompt", "value"}


def clean_display_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_duplicate(value: Any) -> str:
    return re.sub(r"\W+", " ", clean_display_text(value).lower()).strip()


def word_count(value: Any) -> int:
    return len(re.findall(r"\b[\w'-]+\b", clean_display_text(value)))


def classify_lesson_id(lesson_id: str) -> str:
    parts = lesson_id.split(".")
    if len(parts) < 3:
        return NORMAL_LESSON
    if parts[1] == "-1" and parts[2] == "0":
        return MODULE_QUIZ
    if parts[1] == "-1" and parts[2] == "-1":
        return MODULE_OUTRO
    if parts[1] == "0":
        return MODULE_INTRO
    if parts[2] == "0":
        return CHAPTER_INTRO
    if parts[2] == "-1":
        return CHAPTER_OUTRO
    return NORMAL_LESSON


def load_structure_metadata(lesson_root: str | Path) -> dict[str, dict[str, str]]:
    root = Path(lesson_root)
    structure_path = root / "module_structure.json"
    if not structure_path.exists():
        return {}
    structure = load_json(structure_path)
    metadata: dict[str, dict[str, str]] = {}
    for module in structure.get("modules", []):
        module_id = str(module.get("id", ""))
        module_title = clean_display_text(module.get("title", ""))
        for chapter in module.get("chapters", []):
            chapter_id = str(chapter.get("id", ""))
            chapter_title = clean_display_text(chapter.get("title", ""))
            for lesson in chapter.get("lessons", []):
                lesson_id = str(lesson.get("id", ""))
                if not lesson_id:
                    continue
                metadata[lesson_id] = {
                    "module_id": module_id,
                    "chapter_id": chapter_id,
                    "module_title": module_title,
                    "chapter_title": chapter_title,
                    "lesson_title": clean_display_text(lesson.get("title", "")),
                }
    return metadata


def load_structure_lesson_order(lesson_root: str | Path) -> list[str]:
    root = Path(lesson_root)
    structure_path = root / "module_structure.json"
    if not structure_path.exists():
        return []
    structure = load_json(structure_path)
    lesson_ids: list[str] = []
    for module in structure.get("modules", []):
        for chapter in module.get("chapters", []):
            for lesson in chapter.get("lessons", []):
                lesson_id = str(lesson.get("id", ""))
                if lesson_id:
                    lesson_ids.append(lesson_id)
    return lesson_ids


def _lesson_sort_key(lesson_id: str) -> tuple[int, ...]:
    key: list[int] = []
    for part in lesson_id.split("."):
        try:
            value = int(part)
        except ValueError:
            value = 9999
        # Put outro markers after normal numbered lessons in fallback ordering.
        if value < 0:
            value = 9998 + abs(value)
        key.append(value)
    return tuple(key)


def _collect_text(value: Any, output: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"src", "href", "caption", "id", "pollId"}:
                continue
            if key in TEXT_KEYS and isinstance(nested, str):
                text = clean_display_text(nested)
                if text:
                    output.append(text)
            else:
                _collect_text(nested, output)
    elif isinstance(value, list):
        for item in value:
            _collect_text(item, output)


def collect_lesson_text(data: dict[str, Any]) -> str:
    pieces: list[str] = []
    for segment in data.get("segments", []):
        if segment.get("template_id") in {"labels"}:
            continue
        _collect_text(segment.get("content", {}), pieces)
    return "\n".join(pieces)


def _content_items(data: dict[str, Any], template_id: str, key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(data.get("segments", [])):
        if segment.get("template_id") != template_id:
            continue
        for index, item in enumerate(segment.get("content", {}).get(key, []) or [], start=1):
            if isinstance(item, dict):
                item = dict(item)
                item["_segment_index"] = segment_index
                item["_component_index"] = index
                items.append(item)
    return items


def _quiz_questions(data: dict[str, Any]) -> list[dict[str, Any]]:
    return _content_items(data, "scored_quiz", "questions")


def _polls(data: dict[str, Any]) -> list[dict[str, Any]]:
    polls: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(data.get("segments", [])):
        if segment.get("template_id") != "poll":
            continue
        content = dict(segment.get("content", {}) or {})
        content["_segment_index"] = segment_index
        content["_component_index"] = len(polls) + 1
        polls.append(content)
    return polls


def _case_studies(data: dict[str, Any]) -> list[dict[str, Any]]:
    segments = data.get("segments", [])
    studies: list[dict[str, Any]] = []
    stop_templates = {"key_takeaways", "key_resources", "connection_next", "poll", "scored_quiz"}
    for segment_index, segment in enumerate(segments):
        if segment.get("template_id") != "case_study_cover":
            continue
        content = dict(segment.get("content", {}) or {})
        following_text: list[str] = []
        for following in segments[segment_index + 1 :]:
            template_id = following.get("template_id")
            if template_id == "case_study_cover" or template_id in stop_templates:
                break
            _collect_text(following.get("content", {}), following_text)
        content["_segment_index"] = segment_index
        content["_component_index"] = len(studies) + 1
        content["_body_text"] = "\n".join(following_text)
        studies.append(content)
    return studies


def load_review_inputs(
    lesson_root: str | Path,
    lesson_id: str | None = None,
    *,
    start_lesson_id: str | None = None,
    lesson_count: int | None = None,
) -> list[LessonReviewInput]:
    root = Path(lesson_root)
    metadata = load_structure_metadata(root)
    ordered_ids = load_structure_lesson_order(root)
    order_index = {current_id: index for index, current_id in enumerate(ordered_ids)}
    lessons: list[LessonReviewInput] = []
    paths = sorted(
        root.glob("Module_*/*.json"),
        key=lambda path: order_index.get(path.stem, 1_000_000 + sum(_lesson_sort_key(path.stem))),
    )
    for path in paths:
        data = load_json(path)
        current_lesson_id = str(data.get("id") or path.stem)
        if lesson_id and current_lesson_id != lesson_id:
            continue
        meta_source = metadata.get(current_lesson_id, {})
        module_id = meta_source.get("module_id") or current_lesson_id.split(".")[0]
        chapter_id = meta_source.get("chapter_id") or ".".join(current_lesson_id.split(".")[:2])
        meta = LessonMeta(
            lesson_id=current_lesson_id,
            module_id=module_id,
            chapter_id=chapter_id,
            lesson_type=classify_lesson_id(current_lesson_id),
            path=path,
            module_title=meta_source.get("module_title", ""),
            chapter_title=meta_source.get("chapter_title", ""),
            lesson_title=meta_source.get("lesson_title", ""),
        )
        lessons.append(
            LessonReviewInput(
                meta=meta,
                data=data,
                segment_templates=[str(segment.get("template_id", "")) for segment in data.get("segments", [])],
                lesson_text=collect_lesson_text(data),
                takeaways=_content_items(data, "key_takeaways", "takeaways"),
                concepts=_content_items(data, "key_concepts", "concepts"),
                resources=_content_items(data, "key_resources", "resources"),
                quiz_questions=_quiz_questions(data),
                polls=_polls(data),
                case_studies=_case_studies(data),
            )
        )
    if lesson_id:
        return lessons
    if start_lesson_id:
        start_index = next((index for index, lesson in enumerate(lessons) if lesson.meta.lesson_id == start_lesson_id), None)
        if start_index is None:
            raise ValueError(f"Start lesson not found in review inputs: {start_lesson_id}")
        end_index = None if lesson_count is None else start_index + max(lesson_count, 0)
        lessons = lessons[start_index:end_index]
    return lessons
