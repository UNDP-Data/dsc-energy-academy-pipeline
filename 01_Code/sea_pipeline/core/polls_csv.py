from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_core_stage


def run_csv_poll_stage(config: PipelineConfig) -> dict[str, object]:
    return run_core_stage(config, "figma_extraction_export")
