from __future__ import annotations

import unittest
from pathlib import Path
import sys

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.auxiliary.runner import list_auxiliary_stages
from sea_pipeline.core.runner import list_core_stages
from sea_pipeline.photo.runner import list_photo_stages
from sea_pipeline.translation.runner import list_translation_stages


class RunnerStageTests(unittest.TestCase):
    def test_expected_stage_names_are_exposed(self) -> None:
        self.assertIn("structure_generation", list_core_stages())
        self.assertIn("lesson_translation", list_translation_stages())
        self.assertIn("image_upload", list_photo_stages())
        self.assertIn("charts_render", list_auxiliary_stages())
        self.assertIn("resource_image_webp_backfill", list_auxiliary_stages())


if __name__ == "__main__":
    unittest.main()
