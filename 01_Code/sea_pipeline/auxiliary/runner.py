from __future__ import annotations

import json
import time
from typing import Iterable

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.io_json import save_json
from sea_pipeline.shared.notebook_runtime import NotebookStage, execute_notebook_stage

from .avatars.blob_status import write_avatar_blob_status_csv
from .avatars.heygen import run_avatar_script_command
from .charts import functions as chart_functions
from .docx_export import export_docx_materials
from .resource_image_backfill import backfill_resource_webp_images


AUXILIARY_STAGES: dict[str, NotebookStage] = {
    "spellcheck_audit": NotebookStage(
        name="spellcheck_audit",
        notebook_relpath="sea_pipeline/_legacy_notebooks/spellchecker.json",
        cell_indices=(0, 1),
        description="Run the lesson spellcheck audit and write the CSV report.",
    ),
    "indicator_links": NotebookStage(
        name="indicator_links",
        notebook_relpath="sea_pipeline/_legacy_notebooks/spellchecker.json",
        cell_indices=(5,),
        description="Generate source URLs for the indicators workbook via Azure OpenAI.",
    ),
    "polls_generate": NotebookStage(
        name="polls_generate",
        notebook_relpath="sea_pipeline/_legacy_notebooks/polls.json",
        cell_indices=(0, 1),
        description="Generate LLM-based poll registry entries from English lesson content.",
    ),
    "polls_insert": NotebookStage(
        name="polls_insert",
        notebook_relpath="sea_pipeline/_legacy_notebooks/polls.json",
        cell_indices=(3,),
        description="Insert registered polls into English lesson JSON files using anchor matching.",
    ),
    "avatar_script_generation": NotebookStage(
        name="avatar_script_generation",
        notebook_relpath="sea_pipeline/_legacy_notebooks/SEA_Avatar_Scripts_Min.json",
        cell_indices=(1, 2, 3, 4, 5),
        description="Generate avatar script DOCX outputs from English module content.",
    ),
}


def _validate_auxiliary_env(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    validation = config.env.validate_keys(
        [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
        ]
    )
    return {
        "stage": "validate_env",
        "kind": "validation",
        "status": "ok" if validation["ok"] else "warning",
        "summary": validation,
        "duration_seconds": time.time() - started,
    }


def _run_chart_data_stage(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    metadata_path = config.paths.inputs_dir / "Charts" / "Metadata" / "Charts Tracker.xlsx"
    datasets_dir = config.paths.inputs_dir / "Charts" / "Data" / "Charts"
    output_path = config.paths.inputs_dir / "Charts" / "Data" / "Charts" / "charts_data.json"
    metadata = chart_functions.extract_metadata(str(metadata_path))
    datasets = chart_functions.extract_dataset(str(datasets_dir))
    charts = chart_functions.merge_data_metadata(metadata, datasets)
    save_json(charts, output_path)
    return {
        "stage": "charts_extract_and_merge",
        "kind": "python",
        "status": "ok",
        "summary": {"chart_count": len(charts), "output_path": str(output_path)},
        "duration_seconds": time.time() - started,
    }


def _run_chart_render_stage(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    charts_data_path = config.paths.inputs_dir / "Charts" / "Data" / "Charts" / "charts_data.json"
    if charts_data_path.exists():
        charts_data = json.loads(charts_data_path.read_text(encoding="utf-8"))
    else:
        charts_data = chart_functions.merge_data_metadata(
            chart_functions.extract_metadata(str(config.paths.inputs_dir / "Charts" / "Metadata" / "Charts Tracker.xlsx")),
            chart_functions.extract_dataset(str(config.paths.inputs_dir / "Charts" / "Data" / "Charts")),
        )
    charts_config = chart_functions.load_charts_config(str(config.paths.inputs_dir / "Charts" / "Metadata" / "Charts Config.xlsx"))
    template_folder = config.paths.inputs_dir / "Charts" / "Templates"
    light_output = config.paths.outputs_dir / "Charts" / "Auto Charts" / "LightMode"
    dark_output = config.paths.outputs_dir / "Charts" / "Auto Charts" / "DarkMode"
    chart_functions.process_charts(
        charts_data=charts_data,
        charts_config=charts_config,
        template_folder_path=str(template_folder),
        output_dir=str(light_output),
        global_template_path=str(template_folder / "_charts_global_template_light.json"),
    )
    chart_functions.process_charts(
        charts_data=charts_data,
        charts_config=charts_config,
        template_folder_path=str(template_folder),
        output_dir=str(dark_output),
        global_template_path=str(template_folder / "_charts_global_template_dark.json"),
    )
    return {
        "stage": "charts_render",
        "kind": "python",
        "status": "ok",
        "summary": {
            "chart_count": len(charts_data),
            "light_output": str(light_output),
            "dark_output": str(dark_output),
        },
        "duration_seconds": time.time() - started,
    }


def _run_resource_image_webp_backfill_stage(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    if not config.env.sas_url:
        raise ValueError("SAS_URL is required for resource image backfill.")

    lesson_root = config.stage_options.get(
        "resource_image_backfill_lesson_root",
        config.paths.outputs_dir / "SEA_Modules" / "en",
    )
    lesson_glob = str(config.stage_options.get("resource_image_backfill_lesson_glob", "Module_*/*.json"))
    limit = config.stage_options.get("resource_image_backfill_limit")
    overwrite = bool(config.stage_options.get("resource_image_backfill_overwrite", True))

    result = backfill_resource_webp_images(
        lesson_root,
        sas_url=config.env.sas_url,
        lesson_glob=lesson_glob,
        limit=int(limit) if limit is not None else None,
        overwrite=overwrite,
        log=print,
    )
    return {
        "stage": "resource_image_webp_backfill",
        "kind": "python",
        "status": "warning" if result["errors"] else "ok",
        "summary": {
            "lesson_glob": result["lesson_glob"],
            "limit": result["limit"],
            "scanned_resources": result["scanned_resources"],
            "existing_webp": result["existing_webp"],
            "converted_from_png": result["converted_from_png"],
            "missing_both": result["missing_both"],
            "errors": result["errors"],
        },
        "changes": result["changes"],
        "duration_seconds": time.time() - started,
    }


def _run_avatar_blob_status_csv_stage(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    if not config.env.sas_url:
        raise ValueError("SAS_URL is required for avatar blob status CSV generation.")

    input_path = config.stage_options.get(
        "avatar_blob_status_input_path",
        config.paths.inputs_dir / "SEA AI Avatars.csv",
    )
    output_path = config.stage_options.get(
        "avatar_blob_status_output_path",
        config.paths.outputs_dir / "avatars" / "ai_avatar_blob_status.csv",
    )
    result = write_avatar_blob_status_csv(
        input_path=input_path,
        output_path=output_path,
        sas_url=config.env.sas_url,
        log=print,
    )
    return {
        "stage": "avatar_blob_status_csv",
        "kind": "python",
        "status": "warning" if result["partial"] or result["missing"] else "ok",
        "summary": {
            "input_path": result["input_path"],
            "output_path": result["output_path"],
            "expected_rows": result["expected_rows"],
            "lesson_rows": result["lesson_rows"],
            "complete": result["complete"],
            "partial": result["partial"],
            "missing": result["missing"],
        },
        "duration_seconds": time.time() - started,
    }


def list_auxiliary_stages() -> list[str]:
    return [
        "validate_env",
        "charts_extract_and_merge",
        "charts_render",
        "docx_export_text",
        "docx_export_with_images",
        "resource_image_webp_backfill",
        "avatar_blob_status_csv",
        *AUXILIARY_STAGES.keys(),
        "generate_payloads",
        "generate_videos",
        "list_blob_clips",
        "download_blob_clips",
        "add_backgrounds",
    ]


def run_auxiliary_stage(config: PipelineConfig, stage_name: str) -> dict[str, object]:
    if stage_name == "validate_env":
        return _validate_auxiliary_env(config)
    if stage_name == "charts_extract_and_merge":
        return _run_chart_data_stage(config)
    if stage_name == "charts_render":
        return _run_chart_render_stage(config)
    if stage_name == "docx_export_text":
        return export_docx_materials(config, with_images=False)
    if stage_name == "docx_export_with_images":
        return export_docx_materials(config, with_images=True)
    if stage_name == "resource_image_webp_backfill":
        return _run_resource_image_webp_backfill_stage(config)
    if stage_name == "avatar_blob_status_csv":
        return _run_avatar_blob_status_csv_stage(config)
    if stage_name in AUXILIARY_STAGES:
        return execute_notebook_stage(config, AUXILIARY_STAGES[stage_name])
    if stage_name in {"generate_payloads", "generate_videos", "list_blob_clips", "download_blob_clips", "add_backgrounds"}:
        return run_avatar_script_command(config, stage_name)
    raise KeyError(f"Unknown auxiliary stage: {stage_name}")


def run_selected_auxiliary_stages(
    config: PipelineConfig,
    stage_names: Iterable[str],
) -> list[dict[str, object]]:
    return [run_auxiliary_stage(config, stage_name) for stage_name in stage_names]
