from __future__ import annotations

from sea_pipeline.shared.config import PipelineConfig

from .runner import run_photo_stage


def run_image_upload(config: PipelineConfig) -> dict[str, object]:
    return run_photo_stage(config, "image_upload")
