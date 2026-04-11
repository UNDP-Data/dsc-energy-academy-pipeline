from __future__ import annotations

import copy
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient

from .config import PipelineConfig


@dataclass(frozen=True)
class NotebookStage:
    name: str
    notebook_relpath: str
    cell_indices: tuple[int, ...]
    description: str
    prelude_code: str = ""
    strip_lines_by_cell: dict[int, tuple[str, ...]] = field(default_factory=dict)
    extra_code_cells: tuple[str, ...] = ()


def _patched_source(source: str, strip_lines: tuple[str, ...]) -> str:
    if not strip_lines:
        return source
    stripped = {line.strip() for line in strip_lines}
    kept = [line for line in source.splitlines() if line.strip() not in stripped]
    return "\n".join(kept) + ("\n" if source.endswith("\n") else "")


def _collect_output_text(notebook: nbformat.NotebookNode) -> tuple[str, str]:
    stdout: list[str] = []
    stderr: list[str] = []
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            output_type = output.get("output_type")
            if output_type == "stream":
                target = stdout if output.get("name") == "stdout" else stderr
                target.append(output.get("text", ""))
            elif output_type in {"execute_result", "display_data"}:
                data = output.get("data", {})
                if "text/plain" in data:
                    stdout.append(str(data["text/plain"]))
            elif output_type == "error":
                stderr.extend(output.get("traceback", []))
    return "".join(stdout), "".join(stderr)


def _emit_live_output(msg: dict[str, Any]) -> None:
    msg_type = msg.get("msg_type")
    content = msg.get("content", {})
    if msg_type == "stream":
        stream_name = content.get("name", "stdout")
        target = sys.stderr if stream_name == "stderr" else sys.stdout
        print(content.get("text", ""), end="", file=target, flush=True)
        return
    if msg_type in {"execute_result", "display_data"}:
        data = content.get("data", {})
        if "text/plain" in data:
            print(str(data["text/plain"]), flush=True)


def _streaming_client_class(base_client: type[NotebookClient]) -> type[NotebookClient]:
    if not hasattr(base_client, "process_message"):
        return base_client

    class StreamingNotebookClient(base_client):  # type: ignore[misc, valid-type]
        def process_message(self, msg: dict[str, Any], cell: nbformat.NotebookNode, cell_index: int) -> Any:
            output = super().process_message(msg, cell, cell_index)
            _emit_live_output(msg)
            return output

    return StreamingNotebookClient


def execute_notebook_stage(
    config: PipelineConfig,
    stage: NotebookStage,
    kernel_name: str = "python3",
) -> dict[str, Any]:
    notebook_path = config.paths.code_dir / stage.notebook_relpath
    source_notebook = nbformat.read(notebook_path, as_version=4)
    stage_cells = []

    if stage.prelude_code.strip():
        stage_cells.append(nbformat.v4.new_code_cell(stage.prelude_code))

    for cell_index in stage.cell_indices:
        cell = copy.deepcopy(source_notebook.cells[cell_index])
        if cell.cell_type != "code":
            continue
        strip_lines = stage.strip_lines_by_cell.get(cell_index, ())
        cell.source = _patched_source(cell.source, strip_lines)
        stage_cells.append(cell)

    for extra_code in stage.extra_code_cells:
        stage_cells.append(nbformat.v4.new_code_cell(extra_code))

    notebook = nbformat.v4.new_notebook(
        metadata=copy.deepcopy(source_notebook.metadata),
        cells=stage_cells,
    )

    started = time.time()
    client_class = _streaming_client_class(NotebookClient)
    client = client_class(
        notebook,
        kernel_name=kernel_name,
        timeout=config.notebook_timeout_seconds,
        resources={"metadata": {"path": str(config.paths.code_dir)}},
        allow_errors=False,
    )
    client.execute()
    stdout, stderr = _collect_output_text(notebook)

    return {
        "stage": stage.name,
        "kind": "notebook",
        "status": "ok",
        "notebook": stage.notebook_relpath,
        "description": stage.description,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_streamed": client_class is not NotebookClient,
        "stderr_streamed": client_class is not NotebookClient,
        "duration_seconds": time.time() - started,
        "cell_count": len(stage_cells),
    }
