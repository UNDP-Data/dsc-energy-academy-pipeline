from __future__ import annotations

import unittest
from pathlib import Path
import sys

import pandas as pd

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.core.structure import _normalise_metadata_columns, build_module_structure


class CoreStructureTests(unittest.TestCase):
    def test_metadata_type_can_come_from_blank_header_column(self) -> None:
        metadata = pd.DataFrame(
            [
                ["module", 1, "", "Module 1", "#fff", "Module description", "10 min"],
                ["chapter", 1, "1.1", "Chapter 1", "", "Chapter description", "5 min"],
            ],
            columns=["      ", "module_id", "chapter_id", "title", "color", "description", "estimatedTime"],
        )

        normalised = _normalise_metadata_columns(metadata)

        self.assertIn("type", normalised.columns)
        self.assertEqual(normalised["type"].tolist(), ["module", "chapter"])

    def test_build_module_structure_uses_normalised_metadata(self) -> None:
        lessons = pd.DataFrame(
            [
                {
                    "Lesson Number": "1.1.1",
                    "Lesson Title": "Lesson Title",
                    "Chapter Title": "Chapter 1: Chapter Title",
                    "Module Title": "Module 1: Module Title",
                    "Description": "Lesson description",
                }
            ]
        )
        metadata = _normalise_metadata_columns(
            pd.DataFrame(
                [
                    ["module", 1, "", "Module 1", "#fff", "Module description", "10 min"],
                    ["chapter", 1, "1.1", "Chapter 1", "", "Chapter description", "5 min"],
                ],
                columns=["      ", "module_id", "chapter_id", "title", "color", "description", "estimatedTime"],
            )
        )

        structure = build_module_structure(lessons, metadata)

        module = structure["modules"][0]
        self.assertEqual(module["id"], "1")
        self.assertEqual(module["description"], "Module description")
        self.assertEqual(module["chapters"][1]["description"], "Chapter description")
        self.assertEqual(module["chapters"][1]["lessons"][1]["id"], "1.1.1")


if __name__ == "__main__":
    unittest.main()
