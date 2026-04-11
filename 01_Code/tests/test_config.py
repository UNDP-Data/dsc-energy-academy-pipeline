from __future__ import annotations

import unittest
from pathlib import Path
import sys

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.shared.config import PipelineConfig


class PipelineConfigTests(unittest.TestCase):
    def test_from_repo_root_resolves_expected_paths(self) -> None:
        config = PipelineConfig.from_repo_root()
        self.assertTrue(config.paths.code_dir.name == "01_Code")
        self.assertTrue((config.paths.code_dir / "sea_pipeline").exists())
        self.assertTrue(config.root_dir == Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    unittest.main()
