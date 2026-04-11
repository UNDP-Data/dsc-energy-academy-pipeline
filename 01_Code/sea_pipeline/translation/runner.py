from __future__ import annotations

import time
from typing import Iterable

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.notebook_runtime import NotebookStage, execute_notebook_stage


TRANSLATION_STAGES: dict[str, NotebookStage] = {
    "ui_translations": NotebookStage(
        name="ui_translations",
        notebook_relpath="sea_pipeline/_legacy_notebooks/translation-pipeline.json",
        cell_indices=(1,),
        description="Translate UI JSON bundles in language groups.",
    ),
    "module_structure_translation": NotebookStage(
        name="module_structure_translation",
        notebook_relpath="sea_pipeline/_legacy_notebooks/translation-pipeline.json",
        cell_indices=(4,),
        description="Translate module_structure.json into all configured target languages.",
    ),
    "lesson_translation": NotebookStage(
        name="lesson_translation",
        notebook_relpath="sea_pipeline/_legacy_notebooks/translation-pipeline.json",
        cell_indices=(6, 7),
        description="Scan English lesson JSON files, translate them, update backups, and write target-language outputs.",
    ),
    "manual_translation_files": NotebookStage(
        name="manual_translation_files",
        notebook_relpath="sea_pipeline/_legacy_notebooks/translation-pipeline.json",
        cell_indices=(7, 11, 12),
        description="Generate per-language manual translation files for unresolved cache entries.",
        strip_lines_by_cell={7: ("await run_translation_pipeline(retranslate=True)",)},
    ),
    "avatar_script_translation": NotebookStage(
        name="avatar_script_translation",
        notebook_relpath="sea_pipeline/_legacy_notebooks/SEA_Avatar_Scripts_Min.json",
        cell_indices=(7,),
        description="Translate generated avatar scripts into all target languages.",
    ),
}


def _validate_translation_env(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    validation = config.env.validate_keys(
        [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
        ]
    )
    return {
        "stage": "validate_env",
        "kind": "validation",
        "status": "ok" if validation["ok"] else "warning",
        "summary": validation,
        "duration_seconds": time.time() - started,
    }


def list_translation_stages() -> list[str]:
    return ["validate_env", *TRANSLATION_STAGES.keys()]


def run_translation_stage(config: PipelineConfig, stage_name: str) -> dict[str, object]:
    if stage_name == "validate_env":
        return _validate_translation_env(config)
    if stage_name not in TRANSLATION_STAGES:
        raise KeyError(f"Unknown translation stage: {stage_name}")
    return execute_notebook_stage(config, TRANSLATION_STAGES[stage_name])


def run_selected_translation_stages(
    config: PipelineConfig,
    stage_names: Iterable[str],
) -> list[dict[str, object]]:
    return [run_translation_stage(config, stage_name) for stage_name in stage_names]
