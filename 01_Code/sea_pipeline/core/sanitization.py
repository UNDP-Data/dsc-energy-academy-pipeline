from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_core_stage


def run_sanitization(config: PipelineConfig) -> dict[str, object]:
    return run_core_stage(config, "sanitize_json_outputs")
