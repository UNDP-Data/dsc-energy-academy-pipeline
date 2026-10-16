from __future__ import annotations

import re
from typing import Any, MutableMapping

BIDI_TAG_TEMPLATE = '<bdi dir="ltr">{}</bdi>'

_BDI_SPAN_RE = re.compile(r"(<bdi\b[^>]*>.*?</bdi>)", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"(<[^>]+>)")
_URL_RE = re.compile(r"(https?://[^\s<]+|www\.[^\s<]+)")
_ACRONYM_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"("
    r"(?:[A-Z]{2,}\d*s?)"
    r"|(?:[A-Z]{2,}(?:[-/][A-Z0-9]{2,})+s?)"
    r"|(?:[A-Z][A-Za-z]*[A-Z][A-Za-z0-9]*s?)"
    r"|(?:[A-Z]{1,4}\d+[A-Z0-9]*)"
    r"|(?:CO[₂2])"
    r")"
    r"(?![A-Za-z0-9])"
)
_LEGACY_LTR_ISOLATE_RE = re.compile(r"\u2066(.*?)\u2069")


def add_bdi_tags_for_arabic(text: str) -> str:
    """Wrap Latin acronym-like runs in Arabic text with bdi tags for stable rendering."""
    if not isinstance(text, str) or not text:
        return text

    text = _LEGACY_LTR_ISOLATE_RE.sub(lambda match: BIDI_TAG_TEMPLATE.format(match.group(1)), text)
    bdi_parts = _BDI_SPAN_RE.split(text)
    for bdi_index, bdi_part in enumerate(bdi_parts):
        if not bdi_part or _BDI_SPAN_RE.fullmatch(bdi_part):
            continue
        html_parts = _HTML_TAG_RE.split(bdi_part)
        for html_index, html_part in enumerate(html_parts):
            if not html_part or html_part.startswith("<"):
                continue
            html_parts[html_index] = _add_bdi_to_text_segment(html_part)
        bdi_parts[bdi_index] = "".join(html_parts)
    return "".join(bdi_parts)


def isolate_ltr_runs_for_arabic(text: str) -> str:
    """Backward-compatible alias for the Arabic bdi normalizer."""
    return add_bdi_tags_for_arabic(text)


def normalize_arabic_cache_entries(cache: MutableMapping[str, Any]) -> int:
    changed = 0
    for entry in cache.values():
        if not isinstance(entry, MutableMapping):
            continue
        value = entry.get("ar")
        if not isinstance(value, str):
            continue
        normalized = add_bdi_tags_for_arabic(value)
        if normalized != value:
            entry["ar"] = normalized
            changed += 1
    return changed


def _add_bdi_to_text_segment(segment: str) -> str:
    protected: list[str] = []

    def protect_url(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\0url{len(protected) - 1}\0"

    segment = _URL_RE.sub(protect_url, segment)

    def isolate_match(match: re.Match[str]) -> str:
        token = match.group(1)
        return BIDI_TAG_TEMPLATE.format(token)

    segment = _ACRONYM_RE.sub(isolate_match, segment)

    for index, url in enumerate(protected):
        segment = segment.replace(f"\0url{index}\0", url)
    return segment
