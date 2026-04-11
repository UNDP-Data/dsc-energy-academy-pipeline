from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_json import load_json, save_json


def load_figma_json(path: str | Path) -> Any:
    return load_json(path)


def save_figma_json(data: Any, path: str | Path) -> Path:
    return save_json(data, path)
