from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_translation_stage


def run_ui_translations(config: PipelineConfig) -> dict[str, object]:
    return run_translation_stage(config, "ui_translations")
