from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.io_json import load_json, save_json
from sea_pipeline.translation.manual_cache import (
    DEFAULT_TARGET_LANGUAGES,
    extract_manual_translation_payload,
)
from sea_pipeline.translation.progress import cache_language_complete


DEFAULT_ABRIDGED_RATIO = 0.35
DEFAULT_ZH_ABRIDGED_RATIO = 0.12
MIN_ABRIDGED_SOURCE_CHARS = 80
MIN_STOP_TRAILING_PLACEHOLDERS = 5

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
PLACEHOLDER_PREFIX_RE = re.compile(r"^\[needs translation\]\s*", re.IGNORECASE)


def manual_analysis_paths(config: PipelineConfig) -> tuple[Path, Path, Path, Path]:
    inputs = config.paths.inputs_dir
    outputs = config.paths.outputs_dir
    manual_dir_candidates = [
        inputs / "manual-translation-cache",
        outputs / "SEA_Modules" / "Lesson_Translation" / "Manual",
        outputs / "SEA_Modules - backup" / "Lesson_Translation" / "Manual",
    ]
    manual_dir = next(
        (candidate for candidate in manual_dir_candidates if candidate.exists()),
        manual_dir_candidates[0],
    )
    report_dir = outputs / "Lesson_Translation"
    return (
        manual_dir,
        report_dir / "translations_cache.json",
        report_dir / "manual_translation_analysis.json",
        report_dir / "manual_translation_analysis_entries.csv",
    )


def run_manual_translation_analysis(config: PipelineConfig) -> dict[str, Any]:
    manual_dir, cache_file, report_json, report_csv = manual_analysis_paths(config)
    return analyze_manual_translation_directory(
        manual_dir=manual_dir,
        translations_cache_file=cache_file,
        target_languages=config.target_languages,
        output_json=report_json,
        output_csv=report_csv,
    )


def analyze_manual_translation_directory(
    *,
    manual_dir: str | Path,
    translations_cache_file: str | Path | None = None,
    target_languages: Iterable[str] = DEFAULT_TARGET_LANGUAGES,
    output_json: str | Path | None = None,
    output_csv: str | Path | None = None,
    abridged_ratio: float = DEFAULT_ABRIDGED_RATIO,
    zh_abridged_ratio: float = DEFAULT_ZH_ABRIDGED_RATIO,
) -> dict[str, Any]:
    manual_path = Path(manual_dir)
    target_language_set = set(target_languages)
    cache_path = Path(translations_cache_file) if translations_cache_file else None
    translations_cache = _load_cache(cache_path) if cache_path else {}
    cache_order = list(translations_cache.keys())
    cache_index_by_hash = {sentence_hash: index for index, sentence_hash in enumerate(cache_order)}

    files: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    existing_languages = {
        _language_from_manual_filename(file_path)
        for file_path in _manual_json_files(manual_path)
    } if manual_path.exists() else set()
    missing_languages = sorted(lang for lang in target_language_set if lang not in existing_languages)

    if manual_path.exists():
        for file_path in _manual_json_files(manual_path):
            lang = _language_from_manual_filename(file_path)
            if lang not in target_language_set:
                continue
            file_result = analyze_manual_translation_file(
                file_path=file_path,
                language=lang,
                abridged_ratio=zh_abridged_ratio if lang == "zh" else abridged_ratio,
                translations_cache=translations_cache,
                cache_order=cache_order,
                cache_index_by_hash=cache_index_by_hash,
            )
            files.append(file_result)
            entries.extend(file_result["flagged_entries"])

    summary = {
        "stage": "manual_translation_analysis",
        "kind": "analysis",
        "status": "ok" if manual_path.exists() else "warning",
        "manual_dir": str(manual_path),
        "manual_dir_exists": manual_path.exists(),
        "translations_cache_file": str(cache_path) if cache_path else None,
        "translations_cache_exists": cache_path.exists() if cache_path else False,
        "cache_total_entries": len(cache_order),
        "scanned_files": len(files),
        "missing_languages": missing_languages,
        "files": files,
        "completeness": _completeness_rows(files),
        "totals": _aggregate_file_totals(files),
        "output_json": str(output_json) if output_json else None,
        "output_csv": str(output_csv) if output_csv else None,
    }

    if output_json:
        save_json(summary, output_json)
    if output_csv:
        _write_entry_csv(entries, output_csv)

    return summary


def analyze_manual_translation_file(
    *,
    file_path: str | Path,
    language: str,
    abridged_ratio: float = DEFAULT_ABRIDGED_RATIO,
    translations_cache: Mapping[str, Any] | None = None,
    cache_order: list[str] | None = None,
    cache_index_by_hash: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    path = Path(file_path)
    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        return {
            "language": language,
            "file": str(path),
            "status": "invalid_json",
            "total_entries": 0,
            "message": f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            "counts": _count_entry_statuses([]),
            "completion_rate": 0.0,
            "edited_rate": 0.0,
            "stop_point": None,
            "flagged_entries": [],
        }
    if not isinstance(data, Mapping):
        return {
            "language": language,
            "file": str(path),
            "status": "invalid",
            "total_entries": 0,
            "message": "Manual translation file is not a JSON object.",
            "counts": _count_entry_statuses([]),
            "completion_rate": 0.0,
            "edited_rate": 0.0,
            "stop_point": None,
            "flagged_entries": [],
        }

    rows: list[dict[str, Any]] = []
    for index, (sentence_hash, payload) in enumerate(data.items()):
        translation, source_text = _extract_translation_for_language(payload, language)
        source = _source_from_payload(payload, source_text)
        rows.append(
            analyze_manual_translation_entry(
                sentence_hash=str(sentence_hash),
                index=index,
                language=language,
                source=source,
                translation=translation,
                origin=_origin_from_payload(payload),
                abridged_ratio=abridged_ratio,
            )
        )

    counts = _count_entry_statuses(rows)
    cache_summary = _compare_manual_file_to_cache(
        rows=rows,
        language=language,
        translations_cache=translations_cache or {},
        cache_order=cache_order or [],
        cache_index_by_hash=cache_index_by_hash or {},
    )
    stop_point = _detect_stop_point(rows)
    file_status = _classify_file(rows, counts, stop_point)
    flagged_entries = [
        row
        for row in rows
        if row["entry_status"] not in {"complete_candidate"}
    ]

    return {
        "language": language,
        "file": str(path),
        "status": file_status,
        "total_entries": len(rows),
        "counts": counts,
        "completion_rate": _safe_ratio(counts["complete_candidate"], len(rows)),
        "edited_rate": _safe_ratio(len(rows) - counts["placeholder"], len(rows)),
        "cache_summary": cache_summary,
        "stop_point": stop_point,
        "flagged_entries": flagged_entries,
    }


def analyze_manual_translation_entry(
    *,
    sentence_hash: str,
    index: int,
    language: str,
    source: str,
    translation: str,
    origin: str,
    abridged_ratio: float = DEFAULT_ABRIDGED_RATIO,
) -> dict[str, Any]:
    source_norm = _normalize_compare_text(source)
    translation_norm = _normalize_compare_text(translation)
    translation_without_placeholder = _strip_placeholder_prefix(translation_norm)
    source_len = len(source_norm)
    translation_len = len(translation_without_placeholder)
    length_ratio = _safe_ratio(translation_len, source_len)

    entry_status = "complete_candidate"
    reason = ""
    if not translation_norm or "[needs translation]" in translation_norm.lower():
        entry_status = "placeholder"
        reason = "Unresolved placeholder text remains."
    elif source_norm and translation_without_placeholder == source_norm:
        entry_status = "unchanged_source"
        reason = "Manual text still matches the English source."
    elif source_len >= MIN_ABRIDGED_SOURCE_CHARS and length_ratio < abridged_ratio:
        entry_status = "abridged"
        reason = f"Manual text is short relative to source ({length_ratio:.2f})."
    elif source_len >= MIN_ABRIDGED_SOURCE_CHARS and translation_len < 20:
        entry_status = "very_short"
        reason = "Manual text is very short for a long source sentence."

    return {
        "language": language,
        "index": index,
        "hash": sentence_hash,
        "entry_status": entry_status,
        "reason": reason,
        "source": origin,
        "source_chars": source_len,
        "translation_chars": translation_len,
        "length_ratio": round(length_ratio, 3),
        "translation_raw": translation,
        "source_preview": _preview(source_norm),
        "translation_preview": _preview(translation_without_placeholder),
    }


def _classify_file(
    rows: list[dict[str, Any]],
    counts: dict[str, int],
    stop_point: dict[str, Any] | None,
) -> str:
    total = len(rows)
    if total == 0:
        return "empty"
    if counts["complete_candidate"] == 0 and counts["placeholder"] == total:
        return "not_started"
    if counts["placeholder"] == 0 and counts["abridged"] == 0 and counts["very_short"] == 0 and counts["unchanged_source"] == 0:
        return "complete"
    edited_total = total - counts["placeholder"]
    if edited_total and _safe_ratio(counts["abridged"] + counts["very_short"], edited_total) >= 0.2:
        return "abridged_or_low_detail"
    if stop_point:
        return "stopped_mid_file"
    if counts["placeholder"] == 0:
        return "complete_with_flags"
    return "partial_mixed"


def _detect_stop_point(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    edited_indices = [
        row["index"]
        for row in rows
        if row["entry_status"] != "placeholder"
    ]
    if not edited_indices:
        return None

    last_edited_index = max(edited_indices)
    trailing_rows = rows[last_edited_index + 1 :]
    trailing_placeholders = sum(1 for row in trailing_rows if row["entry_status"] == "placeholder")
    if trailing_placeholders < MIN_STOP_TRAILING_PLACEHOLDERS:
        return None
    if trailing_placeholders != len(trailing_rows):
        return None

    return {
        "last_edited_index": last_edited_index,
        "next_unedited_index": last_edited_index + 1,
        "trailing_placeholder_count": trailing_placeholders,
        "last_edited_hash": rows[last_edited_index]["hash"],
        "next_unedited_hash": trailing_rows[0]["hash"] if trailing_rows else None,
        "last_edited_source": rows[last_edited_index]["source"],
        "next_unedited_source": trailing_rows[0]["source"] if trailing_rows else None,
    }


def _aggregate_file_totals(files: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "entries": 0,
        "complete_candidate": 0,
        "placeholder": 0,
        "unchanged_source": 0,
        "abridged": 0,
        "very_short": 0,
    }
    statuses: dict[str, int] = {}
    for file_result in files:
        totals["entries"] += int(file_result.get("total_entries", 0))
        for key, value in file_result.get("counts", {}).items():
            totals[key] = totals.get(key, 0) + int(value)
        status = str(file_result.get("status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
    totals["file_statuses"] = statuses
    return totals


def _completeness_rows(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for file_result in files:
        cache_summary = file_result.get("cache_summary", {})
        rows.append(
            {
                "language": file_result.get("language"),
                "status": file_result.get("status"),
                "manual_entries": file_result.get("total_entries", 0),
                "manual_complete_candidates": file_result.get("counts", {}).get("complete_candidate", 0),
                "manual_placeholders": file_result.get("counts", {}).get("placeholder", 0),
                "edits_vs_cache": cache_summary.get("edits_vs_cache", 0),
                "current_cache_completed": cache_summary.get("current_cache_completed", 0),
                "furthest_edited_cache_index": cache_summary.get("furthest_edited_cache_index"),
                "review_completed_through_cache_entry": cache_summary.get("review_completed_through_cache_entry", 0),
                "review_completion_rate": cache_summary.get("review_completion_rate", 0.0),
                "cache_total_entries": cache_summary.get("cache_total_entries", 0),
                "missing_from_manual": cache_summary.get("missing_from_manual", 0),
                "manual_only_entries": cache_summary.get("manual_only_entries", 0),
            }
        )
    return rows


def _compare_manual_file_to_cache(
    *,
    rows: list[dict[str, Any]],
    language: str,
    translations_cache: Mapping[str, Any],
    cache_order: list[str],
    cache_index_by_hash: Mapping[str, int],
) -> dict[str, Any]:
    manual_hashes = {row["hash"] for row in rows}
    cache_total_entries = len(cache_order)
    edit_rows = []
    manual_only_entries = 0

    for row in rows:
        if row["entry_status"] == "placeholder":
            continue
        sentence_hash = row["hash"]
        cache_entry = translations_cache.get(sentence_hash)
        if not isinstance(cache_entry, Mapping):
            manual_only_entries += 1
            continue

        manual_value = row["translation_raw"]
        cache_value = cache_entry.get(language)
        if not isinstance(cache_value, str):
            cache_value = ""
        if _normalize_cache_compare_value(manual_value) != _normalize_cache_compare_value(cache_value):
            cache_index = cache_index_by_hash.get(sentence_hash)
            edit_rows.append(
                {
                    "hash": sentence_hash,
                    "cache_index": cache_index,
                    "manual_index": row["index"],
                    "source": row["source"],
                    "manual_preview": row["translation_preview"],
                }
            )

    edited_cache_indices = [
        row["cache_index"]
        for row in edit_rows
        if isinstance(row.get("cache_index"), int)
    ]
    furthest_edited_cache_index = max(edited_cache_indices) if edited_cache_indices else None
    review_completed = furthest_edited_cache_index + 1 if furthest_edited_cache_index is not None else 0
    current_cache_completed = sum(
        1 for sentence_hash in cache_order if cache_language_complete(translations_cache.get(sentence_hash), language)
    )

    return {
        "cache_total_entries": cache_total_entries,
        "current_cache_completed": current_cache_completed,
        "cache_entries_present_in_manual": sum(1 for sentence_hash in manual_hashes if sentence_hash in translations_cache),
        "missing_from_manual": max(cache_total_entries - sum(1 for sentence_hash in cache_order if sentence_hash in manual_hashes), 0),
        "manual_only_entries": manual_only_entries,
        "edits_vs_cache": len(edit_rows),
        "furthest_edited_cache_index": furthest_edited_cache_index,
        "review_completed_through_cache_entry": review_completed,
        "review_completion_rate": round(_safe_ratio(review_completed, cache_total_entries), 4),
        "first_edit": edit_rows[0] if edit_rows else None,
        "last_edit": max(
            (row for row in edit_rows if isinstance(row.get("cache_index"), int)),
            key=lambda row: row["cache_index"],
            default=None,
        ),
    }


def _manual_json_files(manual_path: Path) -> list[Path]:
    return sorted(
        file_path
        for file_path in manual_path.glob("*.json")
        if file_path.name.endswith("-manual.json") or not file_path.name.startswith(".")
    )


def _language_from_manual_filename(file_path: Path) -> str:
    return file_path.name.removesuffix("-manual.json").removesuffix(".json")


def _extract_translation_for_language(payload: Any, language: str) -> tuple[str, str]:
    if isinstance(payload, Mapping):
        language_value = payload.get(language)
        if isinstance(language_value, str) and language_value.strip():
            source_text = str(payload.get("en", "") or "")
            return language_value.strip(), source_text
    return extract_manual_translation_payload(payload)


def _load_cache(cache_path: Path | None) -> dict[str, Any]:
    if not cache_path or not cache_path.exists():
        return {}
    try:
        cache = load_json(cache_path)
    except json.JSONDecodeError:
        return {}
    return cache if isinstance(cache, dict) else {}


def _count_entry_statuses(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "complete_candidate": 0,
        "placeholder": 0,
        "unchanged_source": 0,
        "abridged": 0,
        "very_short": 0,
    }
    for row in rows:
        status = row["entry_status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _write_entry_csv(entries: list[dict[str, Any]], output_csv: str | Path) -> None:
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "language",
        "index",
        "hash",
        "entry_status",
        "reason",
        "source",
        "source_chars",
        "translation_chars",
        "length_ratio",
        "source_preview",
        "translation_preview",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow({key: entry.get(key, "") for key in fieldnames})


def _source_from_payload(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        value = payload.get("en")
        if isinstance(value, str):
            return value
    return fallback


def _origin_from_payload(payload: Any) -> str:
    if isinstance(payload, Mapping):
        value = payload.get("source")
        if isinstance(value, str):
            return value
    return ""


def _normalize_compare_text(value: str) -> str:
    no_tags = HTML_TAG_RE.sub(" ", value)
    return html.unescape(WHITESPACE_RE.sub(" ", no_tags)).strip()


def _normalize_cache_compare_value(value: str) -> str:
    return WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _strip_placeholder_prefix(value: str) -> str:
    return PLACEHOLDER_PREFIX_RE.sub("", value).strip()


def _preview(value: str, max_chars: int = 160) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[: max_chars - 1]}..."


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)
