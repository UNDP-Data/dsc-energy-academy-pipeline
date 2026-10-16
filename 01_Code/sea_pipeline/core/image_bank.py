from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sea_pipeline.shared.io_json import load_json, save_json

DEFAULT_IMAGE_BANK_SEED = 20260504
IMAGE_BANK_FILENAME = "academy_image_bank.json"
PLACEHOLDER_TEMPLATE_IDS = {"learning_objectives", "key_takeaways"}
UPLOADED_MODULE_IMAGE_RE = re.compile(
    r"^https://sehseadata\.blob\.core\.windows\.net/images/Modules/Module_\d+/.+\.(?:webp|png|jpe?g)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ImageBankEntry:
    src: str
    source_lesson: str
    source_template: str
    source_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "src": self.src,
            "source_lesson": self.source_lesson,
            "source_template": self.source_template,
            "source_path": self.source_path,
        }


def build_academy_image_bank(lesson_root: str | Path) -> list[dict[str, str]]:
    root = Path(lesson_root)
    seen: set[str] = set()
    entries: list[ImageBankEntry] = []

    for lesson_file in sorted(root.glob("Module_*/*.json")):
        lesson_json = load_json(lesson_file)
        lesson_id = str(lesson_json.get("id") or lesson_file.stem) if isinstance(lesson_json, dict) else lesson_file.stem
        for segment_index, segment in enumerate(_segments_from_lesson(lesson_json)):
            template_id = str(segment.get("template_id", ""))
            if template_id in PLACEHOLDER_TEMPLATE_IDS:
                continue
            for image_path, image in _iter_image_dicts(segment):
                src = image.get("src")
                if not isinstance(src, str) or not _is_bankable_uploaded_image(src):
                    continue
                if src in seen:
                    continue
                seen.add(src)
                entries.append(
                    ImageBankEntry(
                        src=src,
                        source_lesson=lesson_id,
                        source_template=template_id,
                        source_path=f"segments[{segment_index}].{image_path}",
                    )
                )

    return [entry.to_dict() for entry in entries]


def apply_learning_card_image_bank(
    lesson_root: str | Path,
    *,
    seed: int = DEFAULT_IMAGE_BANK_SEED,
    bank_output_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(lesson_root)
    bank = build_academy_image_bank(root)
    if bank_output_path is None:
        bank_output_path = root / IMAGE_BANK_FILENAME
    save_json({"seed": seed, "count": len(bank), "images": bank}, bank_output_path)

    if not bank:
        return {
            "status": "warning",
            "seed": seed,
            "image_bank_count": 0,
            "updated_lessons": 0,
            "updated_cards": 0,
            "bank_output_path": str(bank_output_path),
            "message": "No uploaded academy images found for the image bank.",
        }

    updated_lessons = 0
    updated_cards = 0
    for lesson_file in sorted(root.glob("Module_*/*.json")):
        lesson_json = load_json(lesson_file)
        if not isinstance(lesson_json, dict):
            continue

        lesson_id = str(lesson_json.get("id") or lesson_file.stem)
        lesson_updates = _assign_learning_card_images(lesson_json, lesson_id=lesson_id, bank=bank, seed=seed)
        if lesson_updates:
            save_json(lesson_json, lesson_file)
            updated_lessons += 1
            updated_cards += lesson_updates

    return {
        "status": "ok",
        "seed": seed,
        "image_bank_count": len(bank),
        "updated_lessons": updated_lessons,
        "updated_cards": updated_cards,
        "bank_output_path": str(bank_output_path),
    }


def _assign_learning_card_images(
    lesson_json: dict[str, Any],
    *,
    lesson_id: str,
    bank: list[dict[str, str]],
    seed: int,
) -> int:
    updates = 0
    for segment in _segments_from_lesson(lesson_json):
        template_id = str(segment.get("template_id", ""))
        if template_id == "learning_objectives":
            cards = segment.get("content", {}).get("objectives", [])
        elif template_id == "key_takeaways":
            cards = segment.get("content", {}).get("takeaways", [])
        else:
            continue

        if not isinstance(cards, list):
            continue

        assigned = _stable_bank_order(bank, seed=seed, lesson_id=lesson_id, template_id=template_id)
        for card_index, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            image = card.setdefault("image", {})
            if not isinstance(image, dict):
                card["image"] = image = {}
            next_src = assigned[card_index % len(assigned)]["src"]
            if image.get("src") != next_src or image.get("caption", "") != "":
                image["src"] = next_src
                image["caption"] = ""
                updates += 1

    return updates


def _stable_bank_order(
    bank: list[dict[str, str]],
    *,
    seed: int,
    lesson_id: str,
    template_id: str,
) -> list[dict[str, str]]:
    return sorted(
        bank,
        key=lambda entry: _stable_digest(str(seed), lesson_id, template_id, entry["src"]),
    )


def _stable_digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _segments_from_lesson(lesson_json: Any) -> Iterable[dict[str, Any]]:
    if isinstance(lesson_json, dict) and isinstance(lesson_json.get("segments"), list):
        for segment in lesson_json["segments"]:
            if isinstance(segment, dict):
                yield segment


def _iter_image_dicts(node: Any, path: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        if isinstance(node.get("image"), dict):
            yield f"{path}.image" if path else "image", node["image"]
        for key, value in node.items():
            next_path = f"{path}.{key}" if path else str(key)
            yield from _iter_image_dicts(value, next_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_image_dicts(value, f"{path}[{index}]")


def _is_bankable_uploaded_image(src: str) -> bool:
    return bool(UPLOADED_MODULE_IMAGE_RE.match(src))
