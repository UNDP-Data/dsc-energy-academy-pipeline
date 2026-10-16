from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import pandas as pd


class AvatarBlobContainerProtocol(Protocol):
    def blob_exists(self, blob_name: str) -> bool: ...

    def list_blob_names(self, prefix: str) -> list[str]: ...


class AzureAvatarBlobContainer:
    def __init__(self, sas_url: str) -> None:
        if not sas_url:
            raise ValueError("SAS_URL is required for avatar blob status checks.")
        try:
            from azure.storage.blob import ContainerClient
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "azure-storage-blob is required for avatar blob status checks."
            ) from exc

        self._container_client = ContainerClient.from_container_url(sas_url)

    def blob_exists(self, blob_name: str) -> bool:
        return self._container_client.get_blob_client(blob_name).exists()

    def list_blob_names(self, prefix: str) -> list[str]:
        return [blob.name for blob in self._container_client.list_blobs(name_starts_with=prefix)]


@dataclass(frozen=True)
class AvatarExpectation:
    lesson_id: str
    language: str
    part: str | None = None


def _clean_cell(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text


def _normalise_part(value: Any) -> str | None:
    text = _clean_cell(value)
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric.is_integer():
        return str(int(numeric))
    return text


def load_avatar_expectations(path: str | Path) -> list[AvatarExpectation]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
    else:
        df = pd.read_excel(input_path)

    required = {"Lesson", "Language"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Avatar input is missing required column(s): {', '.join(sorted(missing))}")

    expectations: list[AvatarExpectation] = []
    for _, row in df.iterrows():
        lesson_id = _clean_cell(row.get("Lesson"))
        language = _clean_cell(row.get("Language"))
        if not lesson_id or not language:
            continue
        expectations.append(
            AvatarExpectation(
                lesson_id=lesson_id,
                language=language,
                part=_normalise_part(row.get("Part")) if "Part" in df.columns else None,
            )
        )
    return expectations


def final_avatar_video_blob_name(lesson_id: str, language: str) -> str:
    module_number = lesson_id.split(".")[0]
    return f"Avatars/{language}/{module_number}/Videos/Lesson-{lesson_id}_{language}.mp4"


def heygen_avatar_video_blob_name(lesson_id: str, language: str, part: str) -> str:
    return f"AI_Avatars/Lesson-{lesson_id}_{language}_{part}.mp4"


def heygen_avatar_video_prefix(lesson_id: str, language: str) -> str:
    return f"AI_Avatars/Lesson-{lesson_id}_{language}_"


def avatar_expectation_exists(
    expectation: AvatarExpectation,
    container: AvatarBlobContainerProtocol,
) -> tuple[bool, str]:
    final_blob = final_avatar_video_blob_name(expectation.lesson_id, expectation.language)
    if container.blob_exists(final_blob):
        return True, final_blob

    if expectation.part:
        heygen_blob = heygen_avatar_video_blob_name(
            expectation.lesson_id,
            expectation.language,
            expectation.part,
        )
        if container.blob_exists(heygen_blob):
            return True, heygen_blob
        return False, f"{final_blob} OR {heygen_blob}"

    prefix = heygen_avatar_video_prefix(expectation.lesson_id, expectation.language)
    matches = [name for name in container.list_blob_names(prefix) if name.lower().endswith(".mp4")]
    if matches:
        return True, matches[0]
    return False, f"{final_blob} OR {prefix}*.mp4"


def build_avatar_blob_status_rows(
    expectations: list[AvatarExpectation],
    container: AvatarBlobContainerProtocol,
    *,
    log: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    lesson_totals: dict[str, int] = {}
    lesson_found: dict[str, int] = {}
    lesson_missing: dict[str, list[str]] = {}

    total = len(expectations)
    for index, expectation in enumerate(expectations, start=1):
        lesson_totals[expectation.lesson_id] = lesson_totals.get(expectation.lesson_id, 0) + 1
        lesson_found.setdefault(expectation.lesson_id, 0)
        try:
            exists, matched_or_expected = avatar_expectation_exists(expectation, container)
        except Exception as exc:  # noqa: BLE001 - status CSV should capture audit failures.
            exists = False
            matched_or_expected = f"{type(exc).__name__}: {exc}"

        if exists:
            lesson_found[expectation.lesson_id] += 1
            if log:
                log(f"[{index}/{total}] found {expectation.lesson_id} {expectation.language}: {matched_or_expected}")
        else:
            lesson_missing.setdefault(expectation.lesson_id, []).append(
                f"{expectation.language}{' part ' + expectation.part if expectation.part else ''}: {matched_or_expected}"
            )
            if log:
                log(f"[{index}/{total}] missing {expectation.lesson_id} {expectation.language}: {matched_or_expected}")

    rows: list[dict[str, str]] = []
    for lesson_id in sorted(lesson_totals, key=_lesson_sort_key):
        expected = lesson_totals[lesson_id]
        found = lesson_found.get(lesson_id, 0)
        if found == expected:
            status = f"complete: {found}/{expected} expected avatar video(s) found in blob storage"
        elif found == 0:
            missing = "; ".join(lesson_missing.get(lesson_id, []))
            status = f"missing: 0/{expected} expected avatar video(s) found in blob storage"
            if missing:
                status = f"{status}; {missing}"
        else:
            missing = "; ".join(lesson_missing.get(lesson_id, []))
            status = f"partial: {found}/{expected} expected avatar video(s) found in blob storage"
            if missing:
                status = f"{status}; missing {missing}"
        rows.append({"lesson_id": lesson_id, "status": status})
    return rows


def _lesson_sort_key(lesson_id: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in lesson_id.split("."):
        try:
            values.append(int(part))
        except ValueError:
            values.append(9999)
    return tuple(values)


def write_avatar_blob_status_csv(
    *,
    input_path: str | Path,
    output_path: str | Path,
    sas_url: str | None = None,
    container: AvatarBlobContainerProtocol | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    started = time.time()
    expectations = load_avatar_expectations(input_path)
    blob_container = container or AzureAvatarBlobContainer(sas_url or "")
    rows = build_avatar_blob_status_rows(expectations, blob_container, log=log)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["lesson_id", "status"])
        writer.writeheader()
        writer.writerows(rows)

    complete = sum(1 for row in rows if row["status"].startswith("complete:"))
    partial = sum(1 for row in rows if row["status"].startswith("partial:"))
    missing = sum(1 for row in rows if row["status"].startswith("missing:"))
    return {
        "input_path": str(Path(input_path)),
        "output_path": str(output),
        "expected_rows": len(expectations),
        "lesson_rows": len(rows),
        "complete": complete,
        "partial": partial,
        "missing": missing,
        "duration_seconds": time.time() - started,
    }
