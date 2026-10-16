from __future__ import annotations

import unittest
from pathlib import Path

import nbformat


class DriverNotebookTests(unittest.TestCase):
    def test_driver_notebooks_exist_and_import_runners(self) -> None:
        code_dir = Path(__file__).resolve().parents[1]
        expected = {
            "core-pipeline.ipynb": "run_core_stage",
            "translation-pipeline.ipynb": "run_translation_stage",
            "photo-export.ipynb": "run_photo_stage",
            "auxiliary-pipeline.ipynb": "run_auxiliary_stage",
            "review.ipynb": "run_review_stage",
        }
        for notebook_name, token in expected.items():
            notebook_path = code_dir / notebook_name
            self.assertTrue(notebook_path.exists(), notebook_name)
            notebook = nbformat.read(notebook_path, as_version=4)
            joined = "\n".join(
                "".join(cell.get("source", "")) for cell in notebook.cells if cell.cell_type == "code"
            )
            self.assertIn(token, joined)


if __name__ == "__main__":
    unittest.main()
