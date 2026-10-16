from __future__ import annotations


def normalize_template_name(name: str) -> str:
    return str(name or "").strip().lower()


def build_casefold_frame_class_map(raw_map: dict[str, str]) -> tuple[dict[str, str], set[str]]:
    frame_map: dict[str, str] = {}
    skipped: set[str] = set()
    for name, class_name in raw_map.items():
        normalized = normalize_template_name(name)
        if not normalized:
            continue
        frame_map[normalized] = class_name
    return frame_map, skipped


def resolve_frame_class_name(frame_name: str, frame_class_map: dict[str, object]) -> object | None:
    return frame_class_map.get(normalize_template_name(frame_name))

