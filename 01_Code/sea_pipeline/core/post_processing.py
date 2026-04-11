from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_core_stage


def run_ai_avatar_tagging(config: PipelineConfig) -> dict[str, object]:
    return run_core_stage(config, "ai_avatar_tagging")


def run_lesson_id_export(config: PipelineConfig) -> dict[str, object]:
    return run_core_stage(config, "export_lesson_ids")
