from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _clean_cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _looks_like_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def resolve_resource_href(row: Any) -> str:
    values: dict[str, str] = {}
    for column in ("Link", "Resource Link", "Resource Source"):
        try:
            value = row.get(column, "")
        except AttributeError:
            value = ""
        values[column] = _clean_cell(value)

    for column in ("Link", "Resource Link", "Resource Source"):
        value = values[column]
        if _looks_like_url(value):
            return value

    for column in ("Link", "Resource Link", "Resource Source"):
        value = values[column]
        if value:
            return value
    return ""


def load_resource_lessons_df(
    workbook_path: str | Path,
    csv_fallback_path: str | Path | None = None,
    sheet_name: str = "Lessons",
) -> pd.DataFrame:
    workbook = Path(workbook_path)
    if workbook.exists():
        return pd.read_excel(workbook, sheet_name=sheet_name)

    if csv_fallback_path is not None:
        csv_path = Path(csv_fallback_path)
        if csv_path.exists():
            return pd.read_csv(csv_path)

    raise FileNotFoundError(
        f"Could not find resource lesson source workbook at {workbook}"
        + (
            f" or CSV fallback at {Path(csv_fallback_path)}"
            if csv_fallback_path is not None
            else ""
        )
    )
