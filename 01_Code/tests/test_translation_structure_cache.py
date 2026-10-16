from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.translation.structure_cache import (
    collect_structure_strings,
    format_structure_log_text,
    normalize_structure_source_text,
    run_module_structure_translation,
    structure_cache_hash,
)


class StructureTranslationCacheTests(unittest.TestCase):
    def test_collect_structure_strings_normalizes_and_deduplicates(self) -> None:
        payload = {
            "modules": [
                {
                    "title": " [en] Module Title ",
                    "description": "Shared description",
                    "aiPrompt": "Shared description",
                    "chapters": [
                        {"title": "Chapter Title", "tooltip": "Shared description"},
                    ],
                }
            ]
        }

        strings = collect_structure_strings(payload)

        self.assertEqual(
            strings,
            {"Module Title", "Shared description", "Chapter Title"},
        )

    def test_ai_prompt_reuses_same_structure_cache_entry_as_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "module_structure.json"
            output_dir = tmp_path / "outputs"
            cache_path = tmp_path / "translations_cache.json"
            text = "Shared prompt and description."
            input_path.write_text(
                json.dumps({"modules": [{"description": text, "aiPrompt": text}]}),
                encoding="utf-8",
            )

            calls: list[str] = []

            async def translator(source_text: str) -> dict[str, str]:
                calls.append(source_text)
                return {"fr": f"FR {source_text}", "es": f"ES {source_text}"}

            asyncio.run(
                run_module_structure_translation(
                    input_json=input_path,
                    output_dir=output_dir,
                    target_languages=["fr", "es"],
                    translations_cache_file=cache_path,
                    translator=translator,
                    log=lambda _: None,
                )
            )

            self.assertEqual(calls, [text])
            translated = json.loads((output_dir / "fr" / "module_structure.json").read_text(encoding="utf-8"))
            self.assertEqual(translated["modules"][0]["description"], f"FR {text}")
            self.assertEqual(translated["modules"][0]["aiPrompt"], f"FR {text}")

    def test_module_structure_translation_reuses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "module_structure.json"
            output_dir = tmp_path / "outputs"
            cache_path = tmp_path / "translations_cache.json"
            input_payload = {
                "modules": [
                    {
                        "title": "Module Title",
                        "description": "Module Description",
                    }
                ]
            }
            input_path.write_text(json.dumps(input_payload), encoding="utf-8")
            cache_path.write_text(
                json.dumps(
                    {
                        structure_cache_hash("Module Title"): {
                            "en": "Module Title",
                            "fr": "Titre du module",
                            "es": "Título del módulo",
                        },
                        structure_cache_hash("Module Description"): {
                            "en": "Module Description",
                            "fr": "Description du module",
                            "es": "Descripción del módulo",
                        },
                    }
                ),
                encoding="utf-8",
            )

            calls: list[str] = []

            async def translator(text: str) -> dict[str, str]:
                calls.append(text)
                return {"fr": f"FR {text}", "es": f"ES {text}"}

            result = asyncio.run(
                run_module_structure_translation(
                    input_json=input_path,
                    output_dir=output_dir,
                    target_languages=["fr", "es"],
                    translations_cache_file=cache_path,
                    translator=translator,
                    log=lambda _: None,
                )
            )

            self.assertEqual(calls, [])
            self.assertEqual(result["cache_hits"], 2)
            self.assertEqual(result["translated_now"], 0)
            fr_output = json.loads((output_dir / "fr" / "module_structure.json").read_text(encoding="utf-8"))
            es_output = json.loads((output_dir / "es" / "module_structure.json").read_text(encoding="utf-8"))
            self.assertEqual(fr_output["modules"][0]["title"], "Titre du module")
            self.assertEqual(es_output["modules"][0]["description"], "Descripción del módulo")

    def test_module_structure_translation_writes_new_cache_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "module_structure.json"
            output_dir = tmp_path / "outputs"
            cache_path = tmp_path / "translations_cache.json"
            input_payload = {
                "modules": [
                    {
                        "title": "New Title",
                        "description": "New Description",
                        "chapters": [{"tooltip": "New Tooltip"}],
                    }
                ]
            }
            input_path.write_text(json.dumps(input_payload), encoding="utf-8")

            async def translator(text: str) -> dict[str, str]:
                return {
                    "fr": f"FR::{text}",
                    "es": f"ES::{text}",
                }

            result = asyncio.run(
                run_module_structure_translation(
                    input_json=input_path,
                    output_dir=output_dir,
                    target_languages=["fr", "es"],
                    translations_cache_file=cache_path,
                    translator=translator,
                    log=lambda _: None,
                )
            )

            self.assertEqual(result["cache_hits"], 0)
            self.assertEqual(result["translated_now"], 3)

            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(
                cache[structure_cache_hash("New Title")],
                {"en": "New Title", "fr": "FR::New Title", "es": "ES::New Title"},
            )
            translated = json.loads((output_dir / "fr" / "module_structure.json").read_text(encoding="utf-8"))
            self.assertEqual(translated["modules"][0]["chapters"][0]["tooltip"], "FR::New Tooltip")

    def test_partial_cache_entry_triggers_retranslation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "module_structure.json"
            output_dir = tmp_path / "outputs"
            cache_path = tmp_path / "translations_cache.json"
            input_payload = {"modules": [{"title": "Needs Refresh"}]}
            input_path.write_text(json.dumps(input_payload), encoding="utf-8")
            cache_path.write_text(
                json.dumps(
                    {
                        structure_cache_hash("Needs Refresh"): {
                            "en": "Needs Refresh",
                            "fr": "FR old",
                            "es": "[needs translation] Needs Refresh",
                        }
                    }
                ),
                encoding="utf-8",
            )

            calls: list[str] = []

            async def translator(text: str) -> dict[str, str]:
                calls.append(text)
                return {"fr": "FR new", "es": "ES new"}

            asyncio.run(
                run_module_structure_translation(
                    input_json=input_path,
                    output_dir=output_dir,
                    target_languages=["fr", "es"],
                    translations_cache_file=cache_path,
                    translator=translator,
                    log=lambda _: None,
                )
            )

            self.assertEqual(calls, ["Needs Refresh"])
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cache[structure_cache_hash("Needs Refresh")]["fr"], "FR old")
            self.assertEqual(cache[structure_cache_hash("Needs Refresh")]["es"], "ES new")

    def test_module_structure_translation_uses_full_language_set_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "module_structure.json"
            output_dir = tmp_path / "outputs"
            cache_path = tmp_path / "translations_cache.json"
            input_path.write_text(json.dumps({"modules": [{"title": "Grouped Title"}]}), encoding="utf-8")

            calls: list[tuple[str, tuple[str, ...]]] = []

            async def translator(text: str, languages: list[str]) -> dict[str, str]:
                calls.append((text, tuple(languages)))
                return {lang: f"{lang.upper()}::{text}" for lang in languages}

            asyncio.run(
                run_module_structure_translation(
                    input_json=input_path,
                    output_dir=output_dir,
                    target_languages=["fr", "es", "pt", "ar"],
                    language_groups=[["fr", "es"], ["pt", "ar"]],
                    translations_cache_file=cache_path,
                    translator=translator,
                    log=lambda _: None,
                )
            )

            self.assertEqual(calls, [("Grouped Title", ("fr", "es", "pt", "ar"))])
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(
                cache[structure_cache_hash("Grouped Title")],
                {
                    "en": "Grouped Title",
                    "fr": "FR::Grouped Title",
                    "es": "ES::Grouped Title",
                    "pt": "PT::Grouped Title",
                    "ar": '<bdi dir="ltr">AR</bdi>::Grouped Title',
                },
            )

    def test_module_structure_translation_groups_only_after_full_set_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "module_structure.json"
            output_dir = tmp_path / "outputs"
            cache_path = tmp_path / "translations_cache.json"
            input_path.write_text(json.dumps({"modules": [{"title": "Fallback Title"}]}), encoding="utf-8")

            calls: list[tuple[str, tuple[str, ...]]] = []

            async def translator(text: str, languages: list[str]) -> dict[str, str]:
                calls.append((text, tuple(languages)))
                if languages == ["fr", "es", "pt", "ar"]:
                    return {lang: f"[needs translation] {text}" for lang in languages}
                return {lang: f"{lang.upper()}::{text}" for lang in languages}

            asyncio.run(
                run_module_structure_translation(
                    input_json=input_path,
                    output_dir=output_dir,
                    target_languages=["fr", "es", "pt", "ar"],
                    language_groups=[["fr", "es"], ["pt", "ar"]],
                    translations_cache_file=cache_path,
                    translator=translator,
                    log=lambda _: None,
                )
            )

            self.assertEqual(
                calls,
                [
                    ("Fallback Title", ("fr", "es", "pt", "ar")),
                    ("Fallback Title", ("fr", "es")),
                    ("Fallback Title", ("pt", "ar")),
                ],
            )
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cache[structure_cache_hash("Fallback Title")]["fr"], "FR::Fallback Title")
            self.assertEqual(cache[structure_cache_hash("Fallback Title")]["ar"], '<bdi dir="ltr">AR</bdi>::Fallback Title')

    def test_normalize_structure_source_text_removes_en_prefix(self) -> None:
        self.assertEqual(normalize_structure_source_text(" [en] Example "), "Example")

    def test_normalize_structure_source_text_collapses_hidden_whitespace(self) -> None:
        self.assertEqual(
            normalize_structure_source_text("This\u00a0 text\n\nhas   spacing."),
            "This text has spacing.",
        )

    def test_format_structure_log_text_disambiguates_same_prefixes(self) -> None:
        first = "This chapter highlights data science, AI, and energy modelling tools."
        second = (
            "This chapter highlights data science, AI, and energy modelling tools. "
            "<br> Lesson 1: <strong>Data Science Techniques</strong>."
        )

        first_log = format_structure_log_text(first, limit=64)
        second_log = format_structure_log_text(second, limit=64)

        self.assertNotEqual(first_log.split("]")[0], second_log.split("]")[0])
        self.assertIn(f"len={len(first)}", first_log)
        self.assertIn(f"len={len(second)}", second_log)


if __name__ == "__main__":
    unittest.main()
