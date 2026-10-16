from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.io_json import load_json, save_json
from sea_pipeline.translation.bidi import add_bdi_tags_for_arabic, normalize_arabic_cache_entries

DEFAULT_TARGET_LANGUAGES = ("fr", "es", "pt", "ar", "zh", "ru")


def manual_cache_paths(config: PipelineConfig) -> tuple[Path, Path]:
    outputs = config.paths.outputs_dir
    return (
        outputs / "SEA_Modules" / "Lesson_Translation" / "Manual",
        outputs / "Lesson_Translation" / "translations_cache.json",
    )


def import_manual_translation_cache(
    *,
    manual_dir: str | Path,
    translations_cache_file: str | Path,
    target_languages: Iterable[str] = DEFAULT_TARGET_LANGUAGES,
    import_placeholders: bool = False,
) -> dict[str, Any]:
    manual_path = Path(manual_dir)
    cache_path = Path(translations_cache_file)
    target_language_set = set(target_languages)
    cache = _load_cache(cache_path)

    normalized_existing_arabic = normalize_arabic_cache_entries(cache)
    scanned_files = 0
    imported = 0
    skipped = 0
    changed = normalized_existing_arabic
    per_language: dict[str, int] = {}

    for file_path in sorted(manual_path.glob("*-manual.json")):
        lang = file_path.name.removesuffix("-manual.json")
        if lang not in target_language_set:
            skipped += 1
            continue

        scanned_files += 1
        data = load_json(file_path)
        if not isinstance(data, Mapping):
            skipped += 1
            continue

        for sentence_hash, payload in data.items():
            translation, source_text = extract_manual_translation_payload(payload)
            if not translation:
                skipped += 1
                continue
            if not import_placeholders and "[needs translation]" in translation:
                skipped += 1
                continue

            if lang == "ar":
                translation = add_bdi_tags_for_arabic(translation)

            cache_entry = cache.get(str(sentence_hash))
            if not isinstance(cache_entry, dict):
                cache_entry = {}
            if source_text and not cache_entry.get("en"):
                cache_entry["en"] = source_text

            if cache_entry.get(lang) != translation:
                cache_entry[lang] = translation
                cache[str(sentence_hash)] = cache_entry
                imported += 1
                changed += 1
                per_language[lang] = per_language.get(lang, 0) + 1

    if changed:
        save_json(cache, cache_path)

    return {
        "status": "ok",
        "manual_dir": str(manual_path),
        "translations_cache_file": str(cache_path),
        "scanned_files": scanned_files,
        "imported": imported,
        "skipped": skipped,
        "normalized_existing_arabic": normalized_existing_arabic,
        "per_language": per_language,
        "changed": changed,
    }


def run_manual_translation_cache_import(config: PipelineConfig) -> dict[str, Any]:
    manual_dir, cache_file = manual_cache_paths(config)
    return import_manual_translation_cache(
        manual_dir=manual_dir,
        translations_cache_file=cache_file,
        target_languages=config.target_languages,
    )


def _load_cache(path: Path) -> dict[str, Any]:
    try:
        cache = load_json(path)
    except FileNotFoundError:
        return {}
    return cache if isinstance(cache, dict) else {}


def extract_manual_translation_payload(payload: Any) -> tuple[str, str]:
    if isinstance(payload, str):
        return payload.strip(), ""
    if not isinstance(payload, Mapping):
        return "", ""

    source_text = str(payload.get("en", "") or "")
    for key in ("translation", "translated", "fixed", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), source_text
    return "", source_text


def _extract_manual_translation(payload: Any) -> tuple[str, str]:
    return extract_manual_translation_payload(payload)
