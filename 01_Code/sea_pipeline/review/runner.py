from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.auxiliary.spellcheck import run_spellcheck_audit

from .blob_checks import build_resource_blob_checker
from .controls import DEFAULT_CONTROLS_PATH, load_review_controls
from .extract import load_review_inputs
from .llm import apply_llm_review
from .models import ReviewOutput, ReviewSettings
from .report import write_review_workbook
from .rules import COMPONENTS, DETAIL_COMPONENTS_BY_COMPONENT, run_component_review, run_deterministic_review


@dataclass
class ReviewSession:
    config: PipelineConfig
    settings: ReviewSettings
    lessons: list
    controls: dict
    output: ReviewOutput
    resource_blob_checker: object | None = None


def _default_lesson_root(config: PipelineConfig) -> Path:
    return config.paths.outputs_dir / "SEA_Modules" / "en"


def _default_output_path(config: PipelineConfig) -> Path:
    return config.paths.outputs_dir / "Review" / "academy_review.xlsx"


def _default_cache_path(config: PipelineConfig) -> Path:
    return config.paths.outputs_dir / "Review" / "review_cache.json"


def _default_spellcheck_report_path(config: PipelineConfig) -> Path:
    return config.paths.outputs_dir / "spellcheck_audit_report.csv"


def _raw_test_lesson_count(options: dict[str, object]) -> object:
    return options.get("review_test_lesson_count", False)


def _test_lesson_count_from_options(options: dict[str, object]) -> int:
    raw_count = _raw_test_lesson_count(options)
    if raw_count is False or raw_count is None or raw_count == "":
        return 0
    return int(raw_count)


def _review_ai_mode_from_options(options: dict[str, object]) -> str:
    raw_mode = options.get("review_ai_mode", options.get("review_run_ai_review", options.get("review_use_llm", False)))
    if isinstance(raw_mode, str):
        normalized = raw_mode.strip().lower()
        if normalized in {"", "false", "off", "none", "no", "disabled", "deterministic"}:
            return "off"
        if normalized in {"critical", "crit"}:
            return "critical"
        if normalized in {"true", "on", "yes", "full", "semantic"}:
            return "full"
        raise ValueError("review_ai_mode must be one of: off, full, critical.")
    return "full" if bool(raw_mode) else "off"


def _settings_from_config(config: PipelineConfig, *, force_test_mode: bool | None = None) -> ReviewSettings:
    options = config.stage_options
    test_lesson_count = _test_lesson_count_from_options(options)
    test_mode = test_lesson_count > 0
    if "review_test_mode" in options:
        test_mode = bool(options["review_test_mode"])
    if force_test_mode is not None:
        test_mode = force_test_mode
        if test_mode and test_lesson_count <= 0:
            test_lesson_count = 1
    ai_mode = _review_ai_mode_from_options(options)
    use_llm = ai_mode != "off"
    test_start_lesson_id = str(options.get("review_test_start_lesson_id", options.get("review_test_lesson_id", "1.1.1")))
    return ReviewSettings(
        expect_poll_for_normal_lessons=bool(options.get("review_expect_poll_for_normal_lessons", False)),
        check_resource_blobs=bool(options.get("review_check_resource_blobs", True)),
        use_llm=use_llm,
        ai_mode=ai_mode,
        test_mode=test_mode,
        test_lesson_id=test_start_lesson_id,
        test_start_lesson_id=test_start_lesson_id,
        test_lesson_count=test_lesson_count,
        keep_pass=bool(options.get("review_keep_pass", False)),
        output_path=Path(options.get("review_output_path", _default_output_path(config))),
        cache_path=Path(options.get("review_cache_path", _default_cache_path(config))),
        lesson_root=Path(options.get("review_lesson_root", _default_lesson_root(config))),
        controls_path=Path(options.get("review_controls_path", DEFAULT_CONTROLS_PATH)),
    )


def _validate_review_env(config: PipelineConfig) -> dict[str, object]:
    started = time.time()
    required = []
    ai_mode = _review_ai_mode_from_options(config.stage_options)
    if ai_mode != "off":
        required = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
        ]
    if bool(config.stage_options.get("review_check_resource_blobs", True)):
        required.append("SAS_URL")
    validation = config.env.validate_keys(required) if required else {"ok": True, "missing": [], "values": {}}
    lesson_root = Path(config.stage_options.get("review_lesson_root", _default_lesson_root(config)))
    summary = {
        "env": validation,
        "lesson_root": str(lesson_root),
        "lesson_root_exists": lesson_root.exists(),
        "output_path": str(config.stage_options.get("review_output_path", _default_output_path(config))),
        "cache_path": str(config.stage_options.get("review_cache_path", _default_cache_path(config))),
        "controls_path": str(config.stage_options.get("review_controls_path", DEFAULT_CONTROLS_PATH)),
        "spellcheck_report_path": str(config.stage_options.get("review_spellcheck_report_path", _default_spellcheck_report_path(config))),
        "resource_blob_check": bool(config.stage_options.get("review_check_resource_blobs", True)),
        "test_start_lesson_id": str(config.stage_options.get("review_test_start_lesson_id", config.stage_options.get("review_test_lesson_id", "1.1.1"))),
        "test_lesson_count": _raw_test_lesson_count(config.stage_options),
        "run_ai_review": ai_mode != "off",
        "ai_review_mode": ai_mode,
        "keep_pass": bool(config.stage_options.get("review_keep_pass", False)),
    }
    return {
        "stage": "validate_env",
        "kind": "validation",
        "status": "ok" if validation["ok"] and lesson_root.exists() else "warning",
        "summary": summary,
        "duration_seconds": time.time() - started,
    }


def run_academy_review(
    config: PipelineConfig,
    *,
    test_mode: bool | None = None,
    use_llm: bool | None = None,
    lesson_id: str | None = None,
    log: Callable[[str], None] | None = print,
) -> dict[str, object]:
    started = time.time()
    session = create_review_session(
        config,
        test_mode=test_mode,
        use_llm=use_llm,
        lesson_id=lesson_id,
        log=log,
    )
    for component in COMPONENTS:
        run_review_component(session, component, log=log)
    result = write_review_session_workbook(session, log=log)
    result["duration_seconds"] = time.time() - started
    return result


def create_review_session(
    config: PipelineConfig,
    *,
    test_mode: bool | None = None,
    use_llm: bool | None = None,
    lesson_id: str | None = None,
    log: Callable[[str], None] | None = print,
) -> ReviewSession:
    settings = _settings_from_config(config, force_test_mode=test_mode)
    if use_llm is not None:
        settings.use_llm = use_llm
        settings.ai_mode = "full" if use_llm else "off"
    if lesson_id is not None:
        settings.test_lesson_id = lesson_id
        settings.test_start_lesson_id = lesson_id
        settings.test_lesson_count = 1
        settings.test_mode = True
    selected_lesson_id = settings.test_start_lesson_id if settings.test_mode else None
    if log:
        mode = "test" if settings.test_mode else "full"
        target = f" from {selected_lesson_id} for {settings.test_lesson_count} lesson(s)" if selected_lesson_id else ""
        log(f"[Review] Starting {mode} component review session{target}.")
    lessons = load_review_inputs(
        settings.lesson_root or _default_lesson_root(config),
        start_lesson_id=selected_lesson_id,
        lesson_count=settings.test_lesson_count if settings.test_mode else None,
    )
    controls = load_review_controls(settings.controls_path)
    resource_blob_checker = None
    if settings.check_resource_blobs:
        if config.env.sas_url:
            resource_blob_checker = build_resource_blob_checker(config.env.sas_url)
            if log:
                log("[Review] Resource image blob existence check enabled.")
        elif log:
            log("[Review] Resource image blob existence check skipped: SAS_URL is not set.")
    if log:
        log(f"[Review] Loaded {len(lessons)} lesson JSON file(s).")
        log(f"[Review] Loaded controls: {settings.controls_path}")
    return ReviewSession(
        config=config,
        settings=settings,
        lessons=lessons,
        controls=controls,
        output=ReviewOutput(),
        resource_blob_checker=resource_blob_checker,
    )


def run_review_component(
    session: ReviewSession,
    component: str,
    *,
    log: Callable[[str], None] | None = print,
) -> dict[str, object]:
    started = time.time()
    if component not in COMPONENTS:
        raise KeyError(f"Unknown review component: {component}")
    if log:
        log(f"[Review] Analyzing component: {component}")
    run_component_review(
        session.lessons,
        component,
        output=session.output,
        expect_poll_for_normal_lessons=session.settings.expect_poll_for_normal_lessons,
        controls=session.controls,
        resource_blob_checker=session.resource_blob_checker,
    )
    if session.settings.use_llm:
        apply_llm_review(
            session.output,
            session.lessons,
            session.config,
            session.settings.cache_path or _default_cache_path(session.config),
            controls=session.controls,
            components={component},
            review_mode=session.settings.ai_mode,
            log=log,
        )
    elif log:
        log(f"[Review] LLM semantic review disabled for {component}.")
    failures = sum(1 for row in session.output.lesson_rows if row.get(f"{component}_status") == "fail")
    return {
        "stage": f"review_{component}",
        "kind": "python",
        "status": "warning" if failures else "ok",
        "summary": {
            "component": component,
            "lesson_count": len(session.lessons),
            "component_rows": sum(
                row.get("component") in DETAIL_COMPONENTS_BY_COMPONENT[component]
                for row in session.output.component_rows
            ),
            "component_failures": failures,
            "completed_components": sorted(session.output.completed_components),
        },
        "duration_seconds": time.time() - started,
    }


def write_review_session_workbook(
    session: ReviewSession,
    *,
    log: Callable[[str], None] | None = print,
) -> dict[str, object]:
    started = time.time()
    workbook_path = write_review_workbook(
        session.output,
        session.settings.output_path or _default_output_path(session.config),
        keep_pass=session.settings.keep_pass,
        include_ai_review=session.settings.use_llm,
        spellcheck_csv_path=session.config.stage_options.get(
            "review_spellcheck_report_path",
            _default_spellcheck_report_path(session.config),
        ),
    )
    if log:
        log(f"[Review] Workbook written: {workbook_path}")
    failures = sum(1 for row in session.output.lesson_rows if row.get("overall_status") == "fail")
    selected_lesson_id = session.settings.test_start_lesson_id if session.settings.test_mode else None
    return {
        "stage": "write_review_workbook",
        "kind": "python",
        "status": "warning" if failures else "ok",
        "summary": {
            "test_mode": session.settings.test_mode,
            "test_lesson_id": selected_lesson_id,
            "test_start_lesson_id": selected_lesson_id,
            "test_lesson_count": session.settings.test_lesson_count if session.settings.test_mode else None,
            "lesson_count": len(session.output.lesson_rows),
            "component_rows": len(session.output.component_rows),
            "gaps": len(session.output.gap_rows),
            "overall_failures": failures,
            "completed_components": sorted(session.output.completed_components),
            "llm_enabled": session.settings.use_llm,
            "ai_review_mode": session.settings.ai_mode,
            "llm_cache_hits": session.output.cache_hits,
            "llm_cache_misses": session.output.cache_misses,
            "llm_errors": session.output.llm_errors,
            "output_path": str(workbook_path),
            "cache_path": str(session.output.cache_path or session.settings.cache_path),
            "controls_path": str(session.settings.controls_path),
            "resource_blob_check_enabled": bool(session.resource_blob_checker),
            "resource_blob_check_requested": session.settings.check_resource_blobs,
            "keep_pass": session.settings.keep_pass,
        },
        "duration_seconds": time.time() - started,
    }


def list_review_stages() -> list[str]:
    return [
        "validate_env",
        "test_review",
        "full_review",
        *(f"review_{component}" for component in COMPONENTS),
        "write_review_workbook",
        "spellcheck_audit",
    ]


def run_review_stage(config: PipelineConfig, stage_name: str) -> dict[str, object]:
    if stage_name == "validate_env":
        return _validate_review_env(config)
    if stage_name == "test_review":
        return run_academy_review(config, test_mode=True)
    if stage_name == "full_review":
        return run_academy_review(config, test_mode=False)
    if stage_name.startswith("review_"):
        component = stage_name.removeprefix("review_")
        session = create_review_session(config)
        result = run_review_component(session, component)
        write_review_session_workbook(session)
        return result
    if stage_name == "write_review_workbook":
        session = create_review_session(config)
        return write_review_session_workbook(session)
    if stage_name == "spellcheck_audit":
        return run_spellcheck_audit(config)
    raise KeyError(f"Unknown review stage: {stage_name}")


def run_selected_review_stages(
    config: PipelineConfig,
    stage_names: Iterable[str],
) -> list[dict[str, object]]:
    return [run_review_stage(config, stage_name) for stage_name in stage_names]
