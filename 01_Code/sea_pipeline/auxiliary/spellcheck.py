from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_auxiliary_stage


def run_spellcheck_audit(config: PipelineConfig) -> dict[str, object]:
    return run_auxiliary_stage(config, "spellcheck_audit")
