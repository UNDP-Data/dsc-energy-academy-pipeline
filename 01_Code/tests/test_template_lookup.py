from __future__ import annotations

import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.core.template_lookup import normalize_template_name, resolve_frame_class_name


class TemplateLookupTests(unittest.TestCase):
    def test_normalize_template_name_is_case_insensitive(self) -> None:
        self.assertEqual(normalize_template_name("Chart"), "chart")
        self.assertEqual(normalize_template_name(" chart "), "chart")
        self.assertEqual(normalize_template_name("PHOTO-HORIZONTAL"), "photo-horizontal")

    def test_resolve_frame_class_name_matches_independent_of_case(self) -> None:
        frame_class_map = {
            "chart": "ChartClass",
            "lesson_cover": "LessonCoverClass",
        }
        self.assertEqual(resolve_frame_class_name("Chart", frame_class_map), "ChartClass")
        self.assertEqual(resolve_frame_class_name("chart", frame_class_map), "ChartClass")
        self.assertEqual(resolve_frame_class_name("LESSON_COVER", frame_class_map), "LessonCoverClass")


if __name__ == "__main__":
    unittest.main()
