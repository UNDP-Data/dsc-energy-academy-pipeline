from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import sys
from unittest.mock import patch

import nbformat

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.env import EnvConfig
from sea_pipeline.shared.notebook_runtime import NotebookStage, execute_notebook_stage
from sea_pipeline.shared.paths import RepoPaths


class FakeNotebookClient:
    def __init__(self, notebook, **kwargs):
        self.notebook = notebook
        self.kwargs = kwargs

    def execute(self):
        for cell in self.notebook.cells:
            if cell.cell_type != "code":
                continue
            rendered = cell.source.replace("\n", " | ")
            cell["outputs"] = [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": rendered,
                }
            ]
        return self.notebook


class FakeStreamingNotebookClient:
    def __init__(self, notebook, **kwargs):
        self.notebook = notebook
        self.kwargs = kwargs

    def process_message(self, msg, cell, cell_index):
        if msg["msg_type"] == "stream":
            cell["outputs"] = [
                {
                    "output_type": "stream",
                    "name": msg["content"]["name"],
                    "text": msg["content"]["text"],
                }
            ]
        return None

    def execute(self):
        for idx, cell in enumerate(self.notebook.cells):
            if cell.cell_type != "code":
                continue
            rendered = cell.source.replace("\n", " | ")
            self.process_message(
                {
                    "msg_type": "stream",
                    "content": {"name": "stdout", "text": rendered},
                },
                cell,
                idx,
            )
        return self.notebook


class NotebookRuntimeTests(unittest.TestCase):
    def _make_config(self, root_dir: Path) -> PipelineConfig:
        return PipelineConfig(
            root_dir=root_dir,
            paths=RepoPaths.from_root(root_dir),
            env=EnvConfig.from_environment(load_dotenv_file=False),
            notebook_timeout_seconds=60,
        )

    def test_execute_notebook_stage_runs_selected_cells(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            code_dir = root / "01_Code"
            code_dir.mkdir(parents=True, exist_ok=True)
            notebook_path = code_dir / "sample.ipynb"
            notebook = nbformat.v4.new_notebook()
            notebook.cells = [
                nbformat.v4.new_code_cell('value = 1\nprint("stage one")'),
                nbformat.v4.new_code_cell('print(f"value={value}")'),
            ]
            nbformat.write(notebook, notebook_path)

            with patch("sea_pipeline.shared.notebook_runtime.NotebookClient", FakeNotebookClient):
                result = execute_notebook_stage(
                    self._make_config(root),
                    NotebookStage(
                        name="sample",
                        notebook_relpath="sample.ipynb",
                        cell_indices=(0, 1),
                        description="sample stage",
                    ),
                )

            self.assertEqual(result["status"], "ok")
            self.assertIn('print("stage one")', result["stdout"])
            self.assertIn('print(f"value={value}")', result["stdout"])

    def test_execute_notebook_stage_can_strip_run_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            code_dir = root / "01_Code"
            code_dir.mkdir(parents=True, exist_ok=True)
            notebook_path = code_dir / "sample.ipynb"
            notebook = nbformat.v4.new_notebook()
            notebook.cells = [
                nbformat.v4.new_code_cell(
                    'print("keep")\nprint("remove-me")\n'
                ),
            ]
            nbformat.write(notebook, notebook_path)

            with patch("sea_pipeline.shared.notebook_runtime.NotebookClient", FakeNotebookClient):
                result = execute_notebook_stage(
                    self._make_config(root),
                    NotebookStage(
                        name="sample",
                        notebook_relpath="sample.ipynb",
                        cell_indices=(0,),
                        description="sample stage",
                        strip_lines_by_cell={0: ('print("remove-me")',)},
                    ),
                )

            self.assertIn("keep", result["stdout"])
            self.assertNotIn("remove-me", result["stdout"])

    def test_execute_notebook_stage_streams_output_live_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            code_dir = root / "01_Code"
            code_dir.mkdir(parents=True, exist_ok=True)
            notebook_path = code_dir / "sample.ipynb"
            notebook = nbformat.v4.new_notebook()
            notebook.cells = [
                nbformat.v4.new_code_cell('print("live output")'),
            ]
            nbformat.write(notebook, notebook_path)

            live_stdout = io.StringIO()
            with patch("sea_pipeline.shared.notebook_runtime.NotebookClient", FakeStreamingNotebookClient):
                with redirect_stdout(live_stdout):
                    result = execute_notebook_stage(
                        self._make_config(root),
                        NotebookStage(
                            name="sample",
                            notebook_relpath="sample.ipynb",
                            cell_indices=(0,),
                            description="sample stage",
                        ),
                    )

            self.assertTrue(result["stdout_streamed"])
            self.assertIn('print("live output")', live_stdout.getvalue())
            self.assertIn('print("live output")', result["stdout"])


if __name__ == "__main__":
    unittest.main()
