from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_auxiliary_stage


def run_poll_generation(config: PipelineConfig) -> dict[str, object]:
    return run_auxiliary_stage(config, "polls_generate")


def run_poll_insertion(config: PipelineConfig) -> dict[str, object]:
    return run_auxiliary_stage(config, "polls_insert")
