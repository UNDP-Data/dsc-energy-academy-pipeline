from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

from sea_pipeline.shared.config import PipelineConfig


def _normalize(text: Any) -> str:
    return re.sub(r"[\u202f\xa0]", " ", str(text)).strip()


def _clean_title(text: Any, prefix: str | None = None) -> str:
    clean = _normalize(text)
    return re.sub(prefix, "", clean).strip() if prefix else clean


def _normalise_metadata_columns(metadata: pd.DataFrame) -> pd.DataFrame:
    metadata = metadata.copy()
    stripped_columns = [str(column).strip() for column in metadata.columns]
    metadata.columns = stripped_columns

    if "type" not in metadata.columns:
        first_column = metadata.columns[0]
        first_values = metadata[first_column].astype(str).str.strip().str.lower()
        if first_values.isin({"module", "chapter", ""}).all():
            metadata = metadata.rename(columns={first_column: "type"})

    if "type" not in metadata.columns:
        raise KeyError(
            "Chapters sheet must include a 'type' column, or use the first column for "
            "'module'/'chapter' row markers."
        )

    metadata["type"] = metadata["type"].astype(str).str.strip().str.lower()
    return metadata


def _read_toc_workbook(config: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    workbook_path = config.paths.inputs_dir / "data" / "SEA Table of Contents.xlsx"
    lessons = pd.read_excel(workbook_path, "Lessons").fillna("")
    metadata = pd.read_excel(workbook_path, "Chapters").fillna("")
    return lessons, _normalise_metadata_columns(metadata), workbook_path


def build_module_structure(lessons: pd.DataFrame, metadata: pd.DataFrame) -> dict[str, Any]:
    lessons = lessons.copy()
    lessons = lessons[lessons["Lesson Number"].astype(str).str.strip() != ""]
    lessons["Lesson Number"] = lessons["Lesson Number"].astype(str).str.strip()
    lessons["Module Number"] = lessons["Lesson Number"].apply(lambda value: value.split(".")[0])
    lessons["Chapter Number"] = lessons["Lesson Number"].apply(lambda value: ".".join(value.split(".")[:2]))
    lessons["Module Title"] = lessons["Module Title"].replace("", pd.NA).ffill().fillna("")
    lessons["Chapter Title"] = lessons["Chapter Title"].replace("", pd.NA).ffill().fillna("")

    module_meta = metadata[metadata["type"] == "module"].set_index("module_id").rename_axis(None)
    module_meta.index = module_meta.index.astype(str)
    module_meta = module_meta.to_dict("index")

    chapter_meta = metadata[metadata["type"] == "chapter"].set_index("chapter_id").rename_axis(None)
    chapter_meta.index = chapter_meta.index.astype(str)
    chapter_meta = chapter_meta.to_dict("index")
    lesson_desc = lessons.groupby("Lesson Number")["Description"].first().fillna("").to_dict()

    structure: dict[str, Any] = {"modules": []}

    for module_id, mdf in lessons.groupby("Module Number"):
        module_id = str(module_id)
        meta = module_meta.get(module_id, {})
        module_title = _clean_title(mdf["Module Title"].iloc[0], r"^Module\s*\d+:?\s*")

        module = {
            "id": module_id,
            "title": module_title,
            "color": meta.get("color", ""),
            "icon": f"https://sehseadata.blob.core.windows.net/images/Icons/Modules/module{module_id}.svg",
            "image": {
                "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module{module_id}.webp",
                "caption": "",
            },
            "description": meta.get("description", ""),
            "aiPrompt": meta.get("description", ""),
            "percentComplete": "0",
            "estimatedTime": meta.get("estimatedTime", ""),
            "chapters": [],
        }

        intro_lessons = []
        if module_id == "1":
            intro_lessons.append(
                {
                    "type": "lesson",
                    "title": f"Module {module_id} Preface",
                    "id": f"{module_id}.0.-1",
                    "progress": "not_started",
                    "description": "Preface to the module and overview of what’s ahead.",
                    "aiPrompt": meta.get("description", ""),
                    "image": {
                        "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module{module_id}.webp",
                        "caption": "",
                    },
                }
            )

        intro_lessons.append(
            {
                "type": "lesson",
                "title": f"Module {module_id} Introduction",
                "id": f"{module_id}.0.0",
                "progress": "not_started",
                "description": f"Introduction and learning objectives for Module {module_id}",
                "aiPrompt": meta.get("description", ""),
                "image": {
                    "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module{module_id}.webp",
                    "caption": "",
                },
            }
        )

        module["chapters"].append(
            {
                "id": f"{module_id}.0",
                "title": f"Module {module_id} Introduction",
                "icon": module["icon"],
                "lessons": intro_lessons,
            }
        )

        for chapter_index, (chapter_id, cdf) in enumerate(mdf.groupby("Chapter Number")):
            chapter_id = str(chapter_id)
            chapter_meta_entry = chapter_meta.get(chapter_id, {})
            chapter_title = _clean_title(cdf["Chapter Title"].iloc[0], r"^Chapter\s*\d+:?\s*")

            chapter = {
                "id": chapter_id,
                "title": f"Chapter {chapter_index + 1}: <strong>{chapter_title}</strong>",
                "icon": f"https://sehseadata.blob.core.windows.net/images/Icons/Chapters/chapter{chapter_id}.svg",
                "image": {
                    "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Chapters/chapter{chapter_id}.webp",
                    "caption": "",
                },
                "description": chapter_meta_entry.get("description", ""),
                "aiPrompt": chapter_meta_entry.get("description", ""),
                "estimatedTime": chapter_meta_entry.get("estimatedTime", ""),
                "lessons": [],
            }

            chapter["lessons"].append(
                {
                    "type": "lesson",
                    "title": f"Chapter {chapter_index + 1} Introduction",
                    "id": f"{chapter_id}.0",
                    "progress": "not_started",
                }
            )

            for _, row in cdf.drop_duplicates(subset="Lesson Number").iterrows():
                lesson_id = row["Lesson Number"]
                if pd.isna(row["Lesson Title"]) or lesson_id not in lesson_desc:
                    continue

                lesson_title = f"Lesson {lesson_id[-1]}: <strong>{_clean_title(row['Lesson Title'])}</strong>"
                chapter["lessons"].append(
                    {
                        "type": "lesson",
                        "id": lesson_id,
                        "title": lesson_title,
                        "progress": "not_started",
                        "description": lesson_desc.get(lesson_id, ""),
                        "aiPrompt": lesson_desc.get(lesson_id, ""),
                        "frame": {
                            "src": f"https://sehseadata.blob.core.windows.net/images/Lessons/frame/lesson{lesson_id.replace('.', '')}_frame.webp",
                            "caption": "",
                        },
                        "image": {
                            "src": f"https://sehseadata.blob.core.windows.net/images/Lessons/image/lesson{lesson_id.replace('.', '')}_image.webp",
                            "caption": "",
                        },
                    }
                )

            chapter["lessons"].append(
                {
                    "type": "lesson",
                    "title": f"Chapter {chapter_index + 1} Outro",
                    "id": f"{chapter_id}.-1",
                    "progress": "not_started",
                    "description": "Outro of the chapter and wrap-up.",
                    "aiPrompt": chapter_meta_entry.get("description", ""),
                    "image": {
                        "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Chapters/chapter{chapter_id}.webp",
                        "caption": "",
                    },
                }
            )

            base_desc = chapter_meta_entry.get("description", "")
            lesson_lines = []
            for entry in chapter["lessons"]:
                lesson_id = entry["id"]
                if lesson_id.endswith(".0") or lesson_id.endswith(".-1"):
                    continue
                lesson_lines.append(f"{entry['title']}.")
            chapter["tooltip"] = (
                f"{base_desc} <br> {'<br> '.join(lesson_lines)}" if lesson_lines else base_desc
            )

            module["chapters"].append(chapter)

        quiz_lesson = {
            "type": "lesson",
            "title": f"Module {module_id} Quiz",
            "id": f"{module_id}.-1.0",
            "progress": "not_started",
            "description": "Test your understanding of all lessons in this module.",
            "aiPrompt": meta.get("description", ""),
            "image": {
                "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module{module_id}.webp",
                "caption": "",
            },
        }

        module["chapters"].append(
            {
                "id": f"{module_id}.-1",
                "title": f"Module {module_id} Outro",
                "icon": "https://sehseadata.blob.core.windows.net/images/Icons/module-outro.svg",
                "description": meta.get("description", ""),
                "aiPrompt": meta.get("description", ""),
                "lessons": [
                    quiz_lesson,
                    {
                        "type": "lesson",
                        "title": f"Module {module_id} Outro",
                        "id": f"{module_id}.-1.-1",
                        "progress": "not_started",
                        "image": {
                            "src": f"https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module{module_id}.webp",
                            "caption": "",
                        },
                    },
                ],
            }
        )

        structure["modules"].append(module)

    return structure


def run_structure_generation(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    lessons, metadata, workbook_path = _read_toc_workbook(config)
    output_path = config.paths.outputs_dir / "SEA_Modules" / "en" / "module_structure.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    structure = build_module_structure(lessons, metadata)
    output_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")

    module_count = len(structure["modules"])
    chapter_count = sum(len(module.get("chapters", [])) for module in structure["modules"])
    lesson_count = sum(
        len(chapter.get("lessons", []))
        for module in structure["modules"]
        for chapter in module.get("chapters", [])
    )

    print(f"✅ module_structure.json generated successfully: {output_path}")
    print(f"📚 Modules: {module_count} | Chapters: {chapter_count} | Lessons: {lesson_count}")

    return {
        "stage": "structure_generation",
        "kind": "python",
        "status": "ok",
        "description": "Generate the English module structure from the table-of-contents workbook.",
        "input": str(workbook_path),
        "output": str(output_path),
        "modules": module_count,
        "chapters": chapter_count,
        "lessons": lesson_count,
        "duration_seconds": time.time() - started,
    }
