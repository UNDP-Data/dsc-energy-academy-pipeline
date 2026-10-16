from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


NORMAL_LESSON = "lesson"
MODULE_QUIZ = "module_quiz"
MODULE_OUTRO = "module_outro"
MODULE_INTRO = "module_intro_or_preface"
CHAPTER_INTRO = "chapter_intro"
CHAPTER_OUTRO = "chapter_outro"


@dataclass(frozen=True)
class LessonMeta:
    lesson_id: str
    module_id: str
    chapter_id: str
    lesson_type: str
    path: Path
    module_title: str = ""
    chapter_title: str = ""
    lesson_title: str = ""


@dataclass
class LessonReviewInput:
    meta: LessonMeta
    data: dict[str, Any]
    segment_templates: list[str]
    lesson_text: str
    takeaways: list[dict[str, Any]] = field(default_factory=list)
    concepts: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    quiz_questions: list[dict[str, Any]] = field(default_factory=list)
    polls: list[dict[str, Any]] = field(default_factory=list)
    case_studies: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReviewSettings:
    expect_poll_for_normal_lessons: bool = False
    check_resource_blobs: bool = True
    use_llm: bool = False
    ai_mode: str = "off"
    test_mode: bool = False
    test_lesson_id: str = "1.1.1"
    test_start_lesson_id: str = "1.1.1"
    test_lesson_count: int = 1
    keep_pass: bool = False
    output_path: Path | None = None
    cache_path: Path | None = None
    lesson_root: Path | None = None
    controls_path: Path | None = None


@dataclass
class ReviewOutput:
    lesson_rows: list[dict[str, Any]] = field(default_factory=list)
    component_rows: list[dict[str, Any]] = field(default_factory=list)
    gap_rows: list[dict[str, Any]] = field(default_factory=list)
    summary_rows: list[dict[str, Any]] = field(default_factory=list)
    component_notes: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    completed_components: set[str] = field(default_factory=set)
    output_path: Path | None = None
    cache_path: Path | None = None
    cache_hits: int = 0
    cache_misses: int = 0
    llm_errors: int = 0
