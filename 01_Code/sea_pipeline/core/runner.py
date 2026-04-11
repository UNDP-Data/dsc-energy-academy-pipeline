from __future__ import annotations

import time
from textwrap import dedent
from typing import Iterable

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.notebook_runtime import NotebookStage, execute_notebook_stage


def _figma_stage_prelude(config: PipelineConfig) -> str:
    figma_redownload = bool(config.stage_options.get("figma_redownload", False))
    return dedent(
        f"""
        from pathlib import Path
        Path('../03_Outputs/SEA_Modules/en').mkdir(parents=True, exist_ok=True)
        FIGMA_REDOWNLOAD = {figma_redownload!r}
        print(f"FIGMA_REDOWNLOAD={{FIGMA_REDOWNLOAD}}")
        """
    ).strip()


CORE_STAGES: dict[str, NotebookStage] = {
    "structure_generation": NotebookStage(
        name="structure_generation",
        notebook_relpath="sea_pipeline/_legacy_notebooks/conversion-pipeline.json",
        cell_indices=(0, 1, 2, 3),
        description="Generate the English module structure from the table-of-contents workbook.",
        prelude_code=(
            "from pathlib import Path\n"
            "Path('../03_Outputs/SEA_Modules/en').mkdir(parents=True, exist_ok=True)\n"
        ),
    ),
    "figma_extraction_export": NotebookStage(
        name="figma_extraction_export",
        notebook_relpath="sea_pipeline/_legacy_notebooks/conversion-pipeline.json",
        cell_indices=(0, 1, 2, 7, 9),
        description="Run the main English lesson extraction/export pipeline from cached or downloaded Figma data.",
        strip_lines_by_cell={9: ("run_pipeline(redownload=False)",)},
        extra_code_cells=("run_pipeline(redownload=FIGMA_REDOWNLOAD)",),
    ),
    "ai_avatar_tagging": NotebookStage(
        name="ai_avatar_tagging",
        notebook_relpath="sea_pipeline/_legacy_notebooks/conversion-pipeline.json",
        cell_indices=(13,),
        description="Insert AI avatar video segments into lesson JSON files from the avatar mapping CSV.",
    ),
    "export_lesson_ids": NotebookStage(
        name="export_lesson_ids",
        notebook_relpath="sea_pipeline/_legacy_notebooks/conversion-pipeline.json",
        cell_indices=(17,),
        description="Collect lesson IDs from the English output tree and write the all-lesson ID artifact.",
        prelude_code="import os",
    ),
    "sanitize_json_outputs": NotebookStage(
        name="sanitize_json_outputs",
        notebook_relpath="sea_pipeline/_legacy_notebooks/conversion-pipeline.json",
        cell_indices=(18,),
        description="Scan generated JSON files and sanitize invalid numeric values across language folders.",
    ),
    "overflow_audit": NotebookStage(
        name="overflow_audit",
        notebook_relpath="sea_pipeline/_legacy_notebooks/conversion-pipeline.json",
        cell_indices=(19,),
        description="Audit generated English lesson segments for estimated content overflow.",
    ),
}


def _validate_core_env(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    validation = config.env.validate_keys(
        [
            "FIGMA_TOKEN",
            "FIGMA_DOCUMENT_ID1",
            "FIGMA_DOCUMENT_ID2",
            "FIGMA_DOCUMENT_ID3",
        ]
    )
    return {
        "stage": "validate_env",
        "kind": "validation",
        "status": "ok" if validation["ok"] else "warning",
        "summary": validation,
        "duration_seconds": time.time() - started,
    }


def list_core_stages() -> list[str]:
    return ["validate_env", *CORE_STAGES.keys()]


def run_core_stage(config: PipelineConfig, stage_name: str) -> dict[str, object]:
    if stage_name == "validate_env":
        return _validate_core_env(config)
    if stage_name not in CORE_STAGES:
        raise KeyError(f"Unknown core stage: {stage_name}")
    stage = CORE_STAGES[stage_name]
    if stage_name == "figma_extraction_export":
        stage = NotebookStage(
            name=stage.name,
            notebook_relpath=stage.notebook_relpath,
            cell_indices=stage.cell_indices,
            description=stage.description,
            prelude_code=_figma_stage_prelude(config),
            strip_lines_by_cell=stage.strip_lines_by_cell,
            extra_code_cells=stage.extra_code_cells,
        )
    return execute_notebook_stage(config, stage)


def run_selected_core_stages(config: PipelineConfig, stage_names: Iterable[str]) -> list[dict[str, object]]:
    return [run_core_stage(config, stage_name) for stage_name in stage_names]
