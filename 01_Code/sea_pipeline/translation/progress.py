from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from sea_pipeline.translation.bidi import add_bdi_tags_for_arabic


def cache_entry_complete(cache_entry: Any, target_languages: Iterable[str]) -> bool:
    if not isinstance(cache_entry, Mapping):
        return False

    for lang in target_languages:
        value = cache_entry.get(lang)
        if not isinstance(value, str) or not value.strip():
            return False
        if value.startswith("[needs translation]"):
            return False
    return True


def cache_language_complete(cache_entry: Any, lang: str) -> bool:
    if not isinstance(cache_entry, Mapping):
        return False

    value = cache_entry.get(lang)
    if not isinstance(value, str) or not value.strip():
        return False
    return not value.startswith("[needs translation]")


def missing_cache_languages(cache_entry: Any, target_languages: Iterable[str]) -> list[str]:
    return [lang for lang in target_languages if not cache_language_complete(cache_entry, lang)]


def language_batches_for_missing(
    missing_languages: Iterable[str],
    language_groups: Sequence[Sequence[str]],
) -> list[list[str]]:
    missing = list(missing_languages)
    missing_set = set(missing)
    batches = [[lang for lang in group if lang in missing_set] for group in language_groups]
    batches = [batch for batch in batches if batch]

    covered = {lang for batch in batches for lang in batch}
    extras = [lang for lang in missing if lang not in covered]
    if extras:
        batches.append(extras)

    return batches


def grouped_fallback_batches_after_full_attempt(
    missing_languages: Iterable[str],
    language_groups: Sequence[Sequence[str]],
) -> list[list[str]]:
    missing = list(missing_languages)
    return [batch for batch in language_batches_for_missing(missing, language_groups) if batch != missing]


def merge_translation_batch(
    cache_entry: Any,
    source_text: str,
    language_batch: Iterable[str],
    translated: Mapping[str, Any],
) -> dict[str, str]:
    merged = dict(cache_entry) if isinstance(cache_entry, Mapping) else {}
    merged["en"] = source_text

    for lang in language_batch:
        value = translated.get(lang)
        if isinstance(value, str) and value.strip():
            if lang == "ar":
                value = add_bdi_tags_for_arabic(value)
            merged[lang] = value
        else:
            fallback = f"[needs translation] {source_text}"
            merged[lang] = add_bdi_tags_for_arabic(fallback) if lang == "ar" else fallback

    return merged


def sentence_needs_translation(
    sentence_hash: str,
    translations_cache: Mapping[str, Any],
    target_languages: Iterable[str],
) -> bool:
    return not cache_entry_complete(translations_cache.get(sentence_hash), target_languages)


def count_uncached_sentence_chars(
    sentence_records: Iterable[Mapping[str, Any]],
    translations_cache: Mapping[str, Any],
    target_languages: Iterable[str],
) -> int:
    total = 0
    for record in sentence_records:
        sentence_hash = str(record.get("sentence_hash", ""))
        if sentence_needs_translation(sentence_hash, translations_cache, target_languages):
            total += len(str(record.get("sentence_text", "")))
    return total
