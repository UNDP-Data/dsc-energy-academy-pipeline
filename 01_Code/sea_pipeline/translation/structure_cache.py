from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Sequence

from sea_pipeline.translation.bidi import normalize_arabic_cache_entries
from sea_pipeline.translation.progress import (
    cache_entry_complete,
    grouped_fallback_batches_after_full_attempt,
    merge_translation_batch,
    missing_cache_languages,
)

TRANSLATABLE_STRUCTURE_KEYS = ("title", "description", "tooltip", "aiPrompt")


def load_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(data: Any, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def normalize_structure_source_text(text: str) -> str:
    normalized = re.sub(r"[\u202f\xa0]", " ", str(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.removeprefix("[en]").strip()


def structure_cache_hash(text: str) -> str:
    normalized = normalize_structure_source_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def format_structure_log_text(text: str, limit: int = 90) -> str:
    normalized = normalize_structure_source_text(text)
    digest = structure_cache_hash(normalized)[:12]
    preview = normalized if len(normalized) <= limit else normalized[: limit - 3].rstrip() + "..."
    return f"[{digest} len={len(normalized)}] {preview}"


def collect_structure_strings(
    node: Any,
    keys: Iterable[str] = TRANSLATABLE_STRUCTURE_KEYS,
    collected: set[str] | None = None,
) -> set[str]:
    if collected is None:
        collected = set()

    wanted_keys = set(keys)
    if isinstance(node, dict):
        for key, value in node.items():
            if key in wanted_keys and isinstance(value, str):
                cleaned = normalize_structure_source_text(value)
                if cleaned:
                    collected.add(cleaned)
            elif isinstance(value, (dict, list)):
                collect_structure_strings(value, keys, collected)
    elif isinstance(node, list):
        for item in node:
            collect_structure_strings(item, keys, collected)

    return collected


def load_translation_cache(path: str | Path) -> dict[str, dict[str, str]]:
    try:
        cached = load_json(path)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

    return cached if isinstance(cached, dict) else {}


def get_cached_structure_translation(
    text: str,
    cache: dict[str, dict[str, str]],
    target_languages: Iterable[str],
) -> dict[str, str] | None:
    cache_key = structure_cache_hash(text)
    cached_translation = cache.get(cache_key)
    if not isinstance(cached_translation, dict):
        return None

    result: dict[str, str] = {}
    for lang in target_languages:
        value = cached_translation.get(lang)
        if not isinstance(value, str) or not value.strip() or value.startswith("[needs translation]"):
            return None
        result[lang] = value
    return result


DEFAULT_TARGET_LANGUAGE_GROUPS = (("fr", "es", "pt"), ("ar", "zh", "ru"))


def build_structure_translation_prompt(text: str, target_languages: Iterable[str]) -> str:
    languages = list(target_languages)
    template = json.dumps({lang: "" for lang in languages}, ensure_ascii=False)
    keys = ", ".join(languages)
    return (
        "You are a professional translator. Preserve any HTML tags in the input. "
        f"Translate this text into these target languages only: {keys}. "
        "Return only valid JSON in this exact shape:\n"
        f"{template}\n\n"
        "Text: " + text
    )


def create_structure_translator(
    *,
    api_key: str,
    endpoint: str,
    deployment: str,
    api_version: str,
) -> Callable[[str, Iterable[str]], Awaitable[dict[str, str]]]:
    from openai import AsyncAzureOpenAI

    client = AsyncAzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    async def translate_text(text: str, target_languages: Iterable[str], retries: int = 2) -> dict[str, str]:
        target_languages = list(target_languages)
        prompt = build_structure_translation_prompt(text, target_languages)

        for attempt in range(retries + 1):
            response = await client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": "You are a multilingual translator that outputs only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()

            try:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if not match:
                        raise
                    parsed = json.loads(match.group())

                if not all(isinstance(parsed.get(lang), str) and parsed.get(lang) for lang in target_languages):
                    raise ValueError("Translation JSON missing one or more target language strings")
                return parsed
            except (json.JSONDecodeError, ValueError) as exc:
                print(f"⚠️ Failed to parse translation (attempt {attempt + 1}): {text[:80]}... ({exc})")

                if attempt == retries:
                    raise ValueError(
                        f"Could not parse translation for text: {text[:100]}.\nResponse was:\n{content}"
                    )

        raise RuntimeError("Unreachable translation retry state")

    return translate_text


async def call_structure_translator(
    translator: Callable[..., Awaitable[dict[str, str]]],
    text: str,
    target_languages: Iterable[str],
) -> dict[str, str]:
    signature = inspect.signature(translator)
    positional_params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        }
    ]
    if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in positional_params):
        return await translator(text, list(target_languages))
    if len(positional_params) >= 2:
        return await translator(text, list(target_languages))
    return await translator(text)


async def rebuild_translated_structure_json(
    node: Any,
    *,
    lang: str,
    translations: dict[str, dict[str, str]],
    keys: Iterable[str] = TRANSLATABLE_STRUCTURE_KEYS,
) -> Any:
    wanted_keys = set(keys)
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                result[key] = await rebuild_translated_structure_json(
                    value,
                    lang=lang,
                    translations=translations,
                    keys=keys,
                )
            elif key in wanted_keys and isinstance(value, str):
                normalized = normalize_structure_source_text(value)
                result[key] = translations[normalized][lang] if normalized else value
            else:
                result[key] = value
        return result

    if isinstance(node, list):
        return [
            await rebuild_translated_structure_json(item, lang=lang, translations=translations, keys=keys)
            for item in node
        ]

    return node


async def run_module_structure_translation(
    *,
    input_json: str | Path,
    output_dir: str | Path,
    target_languages: Iterable[str],
    translations_cache_file: str | Path,
    api_key: str | None = None,
    endpoint: str | None = None,
    deployment: str | None = None,
    api_version: str | None = None,
    language_groups: Sequence[Sequence[str]] = DEFAULT_TARGET_LANGUAGE_GROUPS,
    translator: Callable[..., Awaitable[dict[str, str]]] | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    target_languages = list(target_languages)
    original = load_json(input_json)
    unique_strings = sorted(collect_structure_strings(original))
    log(f"📦 Found {len(unique_strings)} unique strings to translate")

    cache = load_translation_cache(translations_cache_file)
    normalized_arabic_entries = normalize_arabic_cache_entries(cache)
    if normalized_arabic_entries:
        save_json(cache, translations_cache_file)
        log(f"🧭 Normalized Arabic bidi isolation in {normalized_arabic_entries} cache entries")
    translations: dict[str, dict[str, str]] = {}
    cache_hits = 0
    translated_now = 0

    if translator is None:
        missing = {
            name: value
            for name, value in {
                "api_key": api_key,
                "endpoint": endpoint,
                "deployment": deployment,
                "api_version": api_version,
            }.items()
            if not value
        }
        if missing:
            raise ValueError(f"Missing Azure translation settings: {', '.join(sorted(missing))}")
        translator = create_structure_translator(
            api_key=api_key,
            endpoint=endpoint,
            deployment=deployment,
            api_version=api_version,
        )

    for text in unique_strings:
        cached = get_cached_structure_translation(text, cache, target_languages)
        if cached is not None:
            cache_hits += 1
            translations[text] = cached
            log(f"♻️ Cache hit: {format_structure_log_text(text)}")
            continue

        cache_key = structure_cache_hash(text)
        cache_entry = cache.get(cache_key)
        missing_languages = missing_cache_languages(cache_entry, target_languages)
        attempted_translation = False

        if missing_languages:
            attempted_translation = True
            log(f"🌍 Translating full set {', '.join(missing_languages)}: {format_structure_log_text(text)}")
            translated = await call_structure_translator(translator, text, missing_languages)
            cache_entry = merge_translation_batch(cache_entry, text, missing_languages, translated)
            cache[cache_key] = cache_entry
            save_json(cache, translations_cache_file)
            log(f"💾 Cache updated for full set {', '.join(missing_languages)}: {format_structure_log_text(text)}")

        remaining_languages = missing_cache_languages(cache_entry, target_languages)
        for language_batch in grouped_fallback_batches_after_full_attempt(remaining_languages, language_groups):
            log(f"🌍 Retrying language batch {', '.join(language_batch)}: {format_structure_log_text(text)}")
            translated = await call_structure_translator(translator, text, language_batch)
            cache_entry = merge_translation_batch(cache_entry, text, language_batch, translated)
            cache[cache_key] = cache_entry
            save_json(cache, translations_cache_file)
            log(f"💾 Cache updated for retry batch {', '.join(language_batch)}: {format_structure_log_text(text)}")

        if not isinstance(cache_entry, dict):
            cache_entry = {"en": text}
        for lang in target_languages:
            cache_entry.setdefault(lang, f"[needs translation] {text}")
        cache[structure_cache_hash(text)] = cache_entry
        translations[text] = {lang: cache_entry[lang] for lang in target_languages}
        if attempted_translation:
            translated_now += 1
        save_json(cache, translations_cache_file)

    for lang in target_languages:
        log(f"🛠 Building translated structure for: {lang}")
        translated_structure = await rebuild_translated_structure_json(
            original,
            lang=lang,
            translations=translations,
        )
        out_path = Path(output_dir) / lang / "module_structure.json"
        save_json(translated_structure, out_path)
        log(f"✅ Saved {lang} version to {out_path}")

    log(f"♻️ Reused {cache_hits} cached strings")
    log(f"🆕 Translated {translated_now} new strings")
    log("🎉 All translations complete.")

    return {
        "status": "ok",
        "unique_strings": len(unique_strings),
        "cache_hits": cache_hits,
        "translated_now": translated_now,
        "target_languages": target_languages,
    }
