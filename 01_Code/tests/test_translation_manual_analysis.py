from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.translation.manual_analysis import (
    analyze_manual_translation_directory,
    analyze_manual_translation_entry,
)


class ManualTranslationAnalysisTests(unittest.TestCase):
    def test_classifies_placeholder_and_unchanged_source(self) -> None:
        placeholder = analyze_manual_translation_entry(
            sentence_hash="hash1",
            index=0,
            language="fr",
            source="Hello world",
            translation="[needs translation] Hello world",
            origin="Module_1/1.1.1.json",
        )
        unchanged = analyze_manual_translation_entry(
            sentence_hash="hash2",
            index=1,
            language="fr",
            source="<strong>Hello</strong> world",
            translation="Hello world",
            origin="Module_1/1.1.1.json",
        )

        self.assertEqual(placeholder["entry_status"], "placeholder")
        self.assertEqual(unchanged["entry_status"], "unchanged_source")

    def test_flags_abridged_translation(self) -> None:
        result = analyze_manual_translation_entry(
            sentence_hash="hash1",
            index=0,
            language="es",
            source=" ".join(["This is a long source sentence with important detail"] * 6),
            translation="Corto.",
            origin="Module_1/1.1.1.json",
        )

        self.assertEqual(result["entry_status"], "abridged")

    def test_detects_stopped_mid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manual_dir = Path(tmp_dir)
            data = {
                "h1": {"en": "One", "text": "Uno", "source": "a.json"},
                "h2": {"en": "Two", "text": "Dos", "source": "a.json"},
            }
            for index in range(3, 10):
                data[f"h{index}"] = {
                    "en": f"Sentence {index}",
                    "text": f"[needs translation] Sentence {index}",
                    "source": "b.json",
                }
            (manual_dir / "es-manual.json").write_text(json.dumps(data), encoding="utf-8")

            result = analyze_manual_translation_directory(
                manual_dir=manual_dir,
                target_languages=["es", "fr"],
                output_json=manual_dir / "report.json",
                output_csv=manual_dir / "report.csv",
            )

            file_result = result["files"][0]
            self.assertEqual(file_result["status"], "stopped_mid_file")
            self.assertEqual(file_result["stop_point"]["last_edited_index"], 1)
            self.assertEqual(result["missing_languages"], ["fr"])
            self.assertTrue((manual_dir / "report.json").exists())
            self.assertTrue((manual_dir / "report.csv").exists())

    def test_detects_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manual_dir = Path(tmp_dir)
            (manual_dir / "fr.json").write_text(
                json.dumps(
                    {
                        "h1": {"en": "Hello", "fr": "Bonjour", "source": "a.json"},
                        "h2": {"en": "Goodbye", "fr": "Au revoir", "source": "a.json"},
                    }
                ),
                encoding="utf-8",
            )

            result = analyze_manual_translation_directory(
                manual_dir=manual_dir,
                target_languages=["fr"],
            )

            self.assertEqual(result["files"][0]["status"], "complete")
            self.assertEqual(result["totals"]["complete_candidate"], 2)

    def test_reports_invalid_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manual_dir = Path(tmp_dir)
            (manual_dir / "ru.json").write_text('{"h1": {"en": "Hello", "ru": "Привет"', encoding="utf-8")

            result = analyze_manual_translation_directory(
                manual_dir=manual_dir,
                target_languages=["ru"],
            )

            self.assertEqual(result["files"][0]["status"], "invalid_json")
            self.assertIn("Invalid JSON", result["files"][0]["message"])

    def test_maps_manual_edits_against_current_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_dir = root / "manual"
            manual_dir.mkdir()
            cache_file = root / "translations_cache.json"
            cache_file.write_text(
                json.dumps(
                    {
                        "h1": {"en": "One", "fr": "Un"},
                        "h2": {"en": "Two", "fr": "Deux"},
                        "h3": {"en": "Three", "fr": "Trois"},
                    }
                ),
                encoding="utf-8",
            )
            (manual_dir / "fr.json").write_text(
                json.dumps(
                    {
                        "h1": {"en": "One", "fr": "Un"},
                        "h2": {"en": "Two", "fr": "Deux corrigé"},
                    }
                ),
                encoding="utf-8",
            )

            result = analyze_manual_translation_directory(
                manual_dir=manual_dir,
                translations_cache_file=cache_file,
                target_languages=["fr"],
            )

            completeness = result["completeness"][0]
            self.assertEqual(completeness["edits_vs_cache"], 1)
            self.assertEqual(completeness["review_completed_through_cache_entry"], 2)
            self.assertEqual(completeness["cache_total_entries"], 3)
            self.assertEqual(completeness["current_cache_completed"], 3)
            self.assertEqual(completeness["missing_from_manual"], 1)


if __name__ == "__main__":
    unittest.main()
