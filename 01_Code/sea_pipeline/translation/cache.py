from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_translation_stage


def run_manual_translation_exports(config: PipelineConfig) -> dict[str, object]:
    return run_translation_stage(config, "manual_translation_files")
