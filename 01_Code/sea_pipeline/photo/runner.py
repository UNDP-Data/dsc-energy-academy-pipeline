from __future__ import annotations

import time
from textwrap import dedent
from typing import Iterable

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.notebook_runtime import NotebookStage, execute_notebook_stage


def _photo_stage_overwrite_prelude(config: PipelineConfig) -> str:
    overwrite = bool(config.stage_options.get("photo_export_overwrite", True))
    return dedent(
        f"""
        PHOTO_EXPORT_OVERWRITE = {overwrite!r}
        print(f"PHOTO_EXPORT_OVERWRITE={{PHOTO_EXPORT_OVERWRITE}}")
        """
    ).strip()


PHOTO_STAGES: dict[str, NotebookStage] = {
    "image_upload": NotebookStage(
        name="image_upload",
        notebook_relpath="sea_pipeline/_legacy_notebooks/photo-export-refactored.json",
        cell_indices=(0, 1, 3),
        description="Scan cached Figma pages and upload referenced lesson images to Azure blob storage.",
    ),
    "infographic_export": NotebookStage(
        name="infographic_export",
        notebook_relpath="sea_pipeline/_legacy_notebooks/photo-export-refactored.json",
        cell_indices=(0, 1, 5),
        description="Export infographics from cached Figma documents and upload them to the configured blob store.",
    ),
}


def _validate_photo_env(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    validation = config.env.validate_keys(
        [
            "FIGMA_TOKEN",
            "FIGMA_DOCUMENT_ID1",
            "FIGMA_DOCUMENT_ID2",
            "FIGMA_DOCUMENT_ID3",
            "SAS_URL",
        ]
    )
    return {
        "stage": "validate_env",
        "kind": "validation",
        "status": "ok" if validation["ok"] else "warning",
        "summary": validation,
        "duration_seconds": time.time() - started,
    }


def list_photo_stages() -> list[str]:
    return ["validate_env", *PHOTO_STAGES.keys()]


def run_photo_stage(config: PipelineConfig, stage_name: str) -> dict[str, object]:
    if stage_name == "validate_env":
        return _validate_photo_env(config)
    if stage_name not in PHOTO_STAGES:
        raise KeyError(f"Unknown photo stage: {stage_name}")
    stage = PHOTO_STAGES[stage_name]
    if stage_name in {"image_upload", "infographic_export"}:
        stage = NotebookStage(
            name=stage.name,
            notebook_relpath=stage.notebook_relpath,
            cell_indices=stage.cell_indices,
            description=stage.description,
            prelude_code=_photo_stage_overwrite_prelude(config),
            strip_lines_by_cell=stage.strip_lines_by_cell,
            extra_code_cells=stage.extra_code_cells,
        )
    return execute_notebook_stage(config, stage)


def run_selected_photo_stages(config: PipelineConfig, stage_names: Iterable[str]) -> list[dict[str, object]]:
    return [run_photo_stage(config, stage_name) for stage_name in stage_names]
