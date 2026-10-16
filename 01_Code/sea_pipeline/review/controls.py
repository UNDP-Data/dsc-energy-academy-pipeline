from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONTROLS_PATH = Path(__file__).with_name("review_controls.csv")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_controls_csv(path: Path) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"section", "key", "value"}
        if not required_columns.issubset(reader.fieldnames or set()):
            raise ValueError(f"Review controls CSV must contain columns: {', '.join(sorted(required_columns))}")
        for row in reader:
            section = str(row.get("section", "")).strip()
            key = str(row.get("key", "")).strip()
            raw_value = str(row.get("value", "")).strip()
            if not section or not key:
                continue
            try:
                value: Any = int(raw_value)
            except ValueError:
                value = raw_value
            controls.setdefault(section, {})[key] = value
    return controls


def load_review_controls(path: str | Path | None = None) -> dict[str, Any]:
    default_controls = _load_controls_csv(DEFAULT_CONTROLS_PATH)
    if path is None:
        return default_controls
    override_path = Path(path)
    if override_path.resolve() == DEFAULT_CONTROLS_PATH.resolve():
        return default_controls
    if not override_path.exists():
        raise FileNotFoundError(f"Review controls file not found: {override_path}")
    override_controls = _load_controls_csv(override_path)
    if not isinstance(override_controls, dict):
        raise ValueError(f"Review controls file must contain CSV rows: {override_path}")
    return _deep_merge(default_controls, override_controls)


def int_control(controls: dict[str, Any], section: str, key: str) -> int:
    value = controls.get(section, {}).get(key)
    if not isinstance(value, int):
        raise ValueError(f"Review control {section}.{key} must be an integer.")
    return value
