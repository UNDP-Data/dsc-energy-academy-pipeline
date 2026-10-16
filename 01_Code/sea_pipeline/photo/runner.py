from __future__ import annotations

import time
from textwrap import dedent
from typing import Iterable

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.notebook_runtime import NotebookStage, execute_notebook_stage
from sea_pipeline.photo.resumable import STANDARD_RUN_MODE, normalize_run_mode


PHOTO_PAGE_SETS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, ("Module 1", "Module 2", "Module 3")),
    (1, ("Module 4", "Module 5", "Module 6")),
    (2, ("Module 7", "Module 8", "Module 9")),
)


def _photo_stage_prelude(config: PipelineConfig, stage_name: str) -> str:
    overwrite = bool(config.stage_options.get("photo_export_overwrite", True))
    run_mode = normalize_run_mode(config.stage_options.get("photo_export_run_mode", STANDARD_RUN_MODE))
    log_dir = config.paths.outputs_dir / "Photo_Export_Logs"
    return dedent(
        f"""
        PHOTO_EXPORT_OVERWRITE = {overwrite!r}
        PHOTO_EXPORT_RUN_MODE = {run_mode!r}
        PHOTO_EXPORT_LOG_DIR = r"{log_dir}"
        print(f"PHOTO_EXPORT_OVERWRITE={{PHOTO_EXPORT_OVERWRITE}}")
        print(f"PHOTO_EXPORT_RUN_MODE={{PHOTO_EXPORT_RUN_MODE}}")
        print(f"PHOTO_EXPORT_LOG_DIR={{PHOTO_EXPORT_LOG_DIR}}")
        """
    ).strip()


PHOTO_STAGES: dict[str, NotebookStage] = {
    "image_upload": NotebookStage(
        name="image_upload",
        notebook_relpath="sea_pipeline/_legacy_notebooks/photo-export-refactored.json",
        cell_indices=(0, 1),
        description="Scan cached Figma pages and upload referenced lesson images to Azure blob storage.",
    ),
    "infographic_export": NotebookStage(
        name="infographic_export",
        notebook_relpath="sea_pipeline/_legacy_notebooks/photo-export-refactored.json",
        cell_indices=(0, 1),
        description="Export infographics from cached Figma documents and upload them to the configured blob store.",
    ),
}


def _photo_stage_setup_cell(stage_name: str) -> str:
    stage_runner = {
        "image_upload": "run_image_upload_page",
        "infographic_export": "run_infographic_export_page",
    }[stage_name]
    return dedent(
        f"""
        from sea_pipeline.photo.resumable import PhotoExportJournal, print_journal_summary, {stage_runner}

        photo_export_journal = PhotoExportJournal.load(PHOTO_EXPORT_LOG_DIR, "{stage_name}")
        print(
            f"🧾 Loaded {stage_name} journal with "
            f"{{len(photo_export_journal.successful_blobs)}} successful uploads, "
            f"{{len(photo_export_journal.missed_blobs)}} unresolved misses, "
            f"{{len(photo_export_journal.completed_pages)}} completed page(s)."
        )
        """
    ).strip()


def _photo_stage_page_cells(stage_name: str) -> tuple[str, ...]:
    page_runner = {
        "image_upload": "run_image_upload_page",
        "infographic_export": "run_infographic_export_page",
    }[stage_name]
    cells: list[str] = []
    for file_index, page_names in PHOTO_PAGE_SETS:
        for page_name in page_names:
            cells.append(
                dedent(
                    f"""
                    result = await {page_runner}(
                        journal=photo_export_journal,
                        file_id=file_page_sets[{file_index}][0],
                        figma_pages=file_page_sets[{file_index}][1],
                        page_name={page_name!r},
                        existing_blobs=existing_blobs,
                        cache_path=cache_path,
                        overwrite=PHOTO_EXPORT_OVERWRITE,
                        run_mode=PHOTO_EXPORT_RUN_MODE,
                        figma_token=FIGMA_TOKEN,
                        calculate_scale=calculate_optimal_scale,
                        {"scan_page=scan_figma_page," if stage_name == "image_upload" else ""}
                        convert_to_webp=convert_image_bytes_to_webp,
                        upload_blob=upload_image_blob,
                        log=print,
                    )
                    """
                ).strip()
            )
    return tuple(cells)


def _photo_stage_final_cell(stage_name: str) -> str:
    return dedent(
        f"""
        print_journal_summary(photo_export_journal, log=print)
        print("✅ {stage_name} pipeline complete.")
        """
    ).strip()


def _build_photo_stage(config: PipelineConfig, stage_name: str) -> NotebookStage:
    stage = PHOTO_STAGES[stage_name]
    return NotebookStage(
        name=stage.name,
        notebook_relpath=stage.notebook_relpath,
        cell_indices=stage.cell_indices,
        description=stage.description,
        prelude_code=_photo_stage_prelude(config, stage_name),
        strip_lines_by_cell=stage.strip_lines_by_cell,
        extra_code_cells=(
            _photo_stage_setup_cell(stage_name),
            *_photo_stage_page_cells(stage_name),
            _photo_stage_final_cell(stage_name),
        ),
    )


def _validate_photo_env(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    validation = config.env.validate_keys(
        [
            "FIGMA_TOKEN",
            "FIGMA_DOCUMENT_ID1",
            "FIGMA_DOCUMENT_ID2",
            "FIGMA_DOCUMENT_ID3",
            "SAS_URL",
        ]
    )
    validation.pop("values", None)
    return {
        "stage": "validate_env",
        "kind": "validation",
        "status": "ok" if validation["ok"] else "warning",
        "summary": validation,
        "duration_seconds": time.time() - started,
    }


def list_photo_stages() -> list[str]:
    return ["validate_env", *PHOTO_STAGES.keys(), "media_optimization"]


def run_photo_stage(config: PipelineConfig, stage_name: str) -> dict[str, object]:
    if stage_name == "media_optimization":
        from sea_pipeline.photo.media_optimization import run_media_optimization

        return run_media_optimization(config)
    if stage_name == "validate_env":
        return _validate_photo_env(config)
    if stage_name not in PHOTO_STAGES:
        raise KeyError(f"Unknown photo stage: {stage_name}")
    stage = _build_photo_stage(config, stage_name)
    return execute_notebook_stage(config, stage)


def run_selected_photo_stages(config: PipelineConfig, stage_names: Iterable[str]) -> list[dict[str, object]]:
    return [run_photo_stage(config, stage_name) for stage_name in stage_names]
