from __future__ import annotations

import random
import re
from typing import Any, Iterable


AI_TAG_SUFFIX = " 💬️"
_FOUR_PLUS_BREAK_PATTERN = re.compile(r"(?:\n\s*){4,}|(?:(?:<br\s*/?>\s*){4,})", re.IGNORECASE)
_TAG_PATTERN = re.compile(r"<[^>]+>")


def normalize_text_for_line_break_validation(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""

    normalized = re.sub(r"^(?:(?:\s*<br\s*/?>\s*)+|(?:\s*(?:\r\n|\r|\n))+)+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?:(?:\s*<br\s*/?>\s*)+|(?:\s*(?:\r\n|\r|\n))+)+$", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"(?:(?:\r\n|\r|\n)\s*){3,}",
        lambda match: "\n\n" if len(re.findall(r"\r\n|\r|\n", match.group(0))) == 3 else match.group(0),
        normalized,
    )
    normalized = re.sub(
        r"(?:(?:<br\s*/?>\s*){3,})",
        lambda match: "<br /><br />" if len(re.findall(r"<br\s*/?>", match.group(0), flags=re.IGNORECASE)) == 3 else match.group(0),
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized.strip()


def apply_ai_keyword_tags(
    segments: list[dict[str, Any]],
    entity_keywords: Iterable[str],
    prompts: list[str],
) -> list[dict[str, Any]]:
    used_keywords = set()
    sorted_keywords = sorted({str(keyword).strip() for keyword in entity_keywords if str(keyword).strip()}, key=lambda x: -len(x))

    for segment in segments:
        if segment.get("template_id") != "text":
            continue

        content = segment.get("content", {})
        text_elements = content.get("text_elements", [])
        if not isinstance(text_elements, list):
            continue

        tagged_this_frame = False
        for te in text_elements:
            if tagged_this_frame:
                break
            te_content = te.get("content", {})
            original_text = te_content.get("text", "")
            if not isinstance(original_text, str):
                continue

            for keyword in sorted_keywords:
                if keyword in used_keywords:
                    continue
                match = re.search(rf"\b({re.escape(keyword)})\b", original_text, flags=re.IGNORECASE)
                if not match:
                    continue

                matched_text = match.group(1)
                prompt = prompts[0].format(keyword=matched_text) if len(prompts) == 1 else random.choice(prompts).format(keyword=matched_text)
                ai_tag = f'<ai prompt="{prompt}">{matched_text}{AI_TAG_SUFFIX}</ai>'
                new_text = re.sub(
                    rf"\b({re.escape(keyword)})\b",
                    ai_tag,
                    original_text,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if new_text == original_text:
                    continue

                te["content"]["text"] = new_text
                used_keywords.add(keyword)
                tagged_this_frame = True
                break

    return segments


def _plain_text_snippet(text: str) -> str:
    normalized = _TAG_PATTERN.sub("", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) <= 48:
        return normalized
    return normalized[:45].rstrip() + "..."


def find_triple_line_break_issues(obj: Any, path: str = "$") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            issues.extend(find_triple_line_break_issues(value, f"{path}.{key}"))
        return issues

    if isinstance(obj, list):
        for idx, value in enumerate(obj):
            issues.extend(find_triple_line_break_issues(value, f"{path}[{idx}]"))
        return issues

    if not isinstance(obj, str):
        return issues

    normalized_obj = normalize_text_for_line_break_validation(obj)

    for match in _FOUR_PLUS_BREAK_PATTERN.finditer(normalized_obj):
        before = _plain_text_snippet(normalized_obj[max(0, match.start() - 80):match.start()])
        after = _plain_text_snippet(normalized_obj[match.end():match.end() + 80])
        issues.append(
            {
                "path": path,
                "before": before,
                "after": after,
                "message": (
                    f"4+ line break run at {path} "
                    f"between '{before or '[start]'}' and '{after or '[end]'}'"
                ),
            }
        )

    return issues
