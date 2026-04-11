from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_auxiliary_stage


def run_docx_export(config: PipelineConfig, with_images: bool = False) -> dict[str, object]:
    stage_name = "docx_export_with_images" if with_images else "docx_export_text"
    return run_auxiliary_stage(config, stage_name)
