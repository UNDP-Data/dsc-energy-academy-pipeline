from __future__ import annotations

import asyncio
import csv
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp
import requests


PhotoLogFn = Callable[[str], None]
ScaleCalculator = Callable[[float], float]
ScanPageFn = Callable[[dict[str, Any]], dict[str, dict[str, Any]]]
ConvertToWebpFn = Callable[[bytes], bytes]
UploadBlobFn = Callable[[str, bytes], Awaitable[str]]

STANDARD_RUN_MODE = "standard"
RETRY_MISSED_RUN_MODE = "retry_missed"
VALID_RUN_MODES = {STANDARD_RUN_MODE, RETRY_MISSED_RUN_MODE}


def normalize_run_mode(value: object) -> str:
    mode = str(value or STANDARD_RUN_MODE).strip().lower()
    if mode not in VALID_RUN_MODES:
        raise ValueError(
            f"Unsupported photo export run mode: {value!r}. "
            f"Expected one of: {', '.join(sorted(VALID_RUN_MODES))}."
        )
    return mode


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_exception(exc: BaseException) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def page_key(file_id: str, page_name: str) -> str:
    return f"{file_id}::{page_name}"


def normalize_blob_name(blob_name: str) -> str:
    return blob_name.replace(" ", "_")


def _default_snapshot_interval() -> int:
    return 25


@dataclass
class PhotoExportJournal:
    log_dir: Path
    stage_name: str
    snapshot_interval: int = field(default_factory=_default_snapshot_interval)
    successful_blobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    missed_blobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    completed_pages: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_snapshot_changes: int = 0

    @property
    def events_path(self) -> Path:
        return self.log_dir / f"{self.stage_name}_events.jsonl"

    @property
    def summary_path(self) -> Path:
        return self.log_dir / f"{self.stage_name}_summary.json"

    @property
    def missed_json_path(self) -> Path:
        return self.log_dir / f"{self.stage_name}_missed.json"

    @property
    def missed_csv_path(self) -> Path:
        return self.log_dir / f"{self.stage_name}_missed.csv"

    @classmethod
    def load(cls, log_dir: str | Path, stage_name: str) -> "PhotoExportJournal":
        journal = cls(log_dir=Path(log_dir).resolve(), stage_name=stage_name)
        journal.log_dir.mkdir(parents=True, exist_ok=True)
        if journal.events_path.exists():
            with journal.events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    journal._apply_event(json.loads(line))
        journal.flush_snapshots(force=True)
        return journal

    def summary_payload(self) -> dict[str, Any]:
        return {
            "stage": self.stage_name,
            "updated_at": utc_now_iso(),
            "successful_count": len(self.successful_blobs),
            "missed_count": len(self.missed_blobs),
            "completed_page_count": len(self.completed_pages),
            "completed_pages": self.completed_pages,
            "missed_blobs": list(self.missed_blobs.values()),
        }

    def is_successful(self, blob_name: str) -> bool:
        return normalize_blob_name(blob_name) in self.successful_blobs

    def is_missed(self, blob_name: str) -> bool:
        return normalize_blob_name(blob_name) in self.missed_blobs

    def page_is_completed(self, file_id: str, page_name: str) -> bool:
        return page_key(file_id, page_name) in self.completed_pages

    def record_success(
        self,
        *,
        blob_name: str,
        node_id: str,
        file_id: str,
        page_name: str,
        url: str,
    ) -> None:
        event = {
            "event": "success",
            "timestamp": utc_now_iso(),
            "blob_name": normalize_blob_name(blob_name),
            "node_id": node_id,
            "file_id": file_id,
            "page_name": page_name,
            "url": url,
        }
        self._append_event(event)
        self.flush_snapshots()

    def record_miss(
        self,
        *,
        blob_name: str,
        node_id: str,
        file_id: str,
        page_name: str,
        reason: str,
        detail: str,
        url: str | None = None,
    ) -> None:
        event = {
            "event": "missed",
            "timestamp": utc_now_iso(),
            "blob_name": normalize_blob_name(blob_name),
            "node_id": node_id,
            "file_id": file_id,
            "page_name": page_name,
            "reason": reason,
            "detail": detail,
            "url": url or "",
        }
        self._append_event(event)
        self.flush_snapshots(force=True)

    def record_page_completed(
        self,
        *,
        file_id: str,
        page_name: str,
        summary: dict[str, Any],
    ) -> None:
        event = {
            "event": "page_completed",
            "timestamp": utc_now_iso(),
            "page_key": page_key(file_id, page_name),
            "file_id": file_id,
            "page_name": page_name,
            "summary": summary,
        }
        self._append_event(event)
        self.flush_snapshots(force=True)

    def _append_event(self, event: dict[str, Any]) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._apply_event(event)

    def _apply_event(self, event: dict[str, Any]) -> None:
        self.pending_snapshot_changes += 1
        event_type = event.get("event")
        if event_type == "success":
            blob_name = normalize_blob_name(str(event["blob_name"]))
            self.successful_blobs[blob_name] = event
            self.missed_blobs.pop(blob_name, None)
            return
        if event_type == "missed":
            blob_name = normalize_blob_name(str(event["blob_name"]))
            if blob_name not in self.successful_blobs:
                self.missed_blobs[blob_name] = event
            return
        if event_type == "page_completed":
            self.completed_pages[str(event["page_key"])] = {
                "file_id": event["file_id"],
                "page_name": event["page_name"],
                "timestamp": event["timestamp"],
                "summary": event["summary"],
            }

    def flush_snapshots(self, force: bool = False) -> None:
        if not force and self.pending_snapshot_changes < self.snapshot_interval:
            return
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(
            json.dumps(self.summary_payload(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.missed_json_path.write_text(
            json.dumps(list(self.missed_blobs.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        with self.missed_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "timestamp",
                    "file_id",
                    "page_name",
                    "node_id",
                    "blob_name",
                    "reason",
                    "detail",
                    "url",
                ],
            )
            writer.writeheader()
            for record in sorted(
                self.missed_blobs.values(),
                key=lambda item: (
                    str(item.get("page_name", "")),
                    str(item.get("blob_name", "")),
                ),
            ):
                writer.writerow(
                    {
                        "timestamp": record.get("timestamp", ""),
                        "file_id": record.get("file_id", ""),
                        "page_name": record.get("page_name", ""),
                        "node_id": record.get("node_id", ""),
                        "blob_name": record.get("blob_name", ""),
                        "reason": record.get("reason", ""),
                        "detail": record.get("detail", ""),
                        "url": record.get("url", ""),
                    }
                )
        self.pending_snapshot_changes = 0


def load_json_file(path: str | Path, default: Any) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json_file(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def select_scanned_nodes(
    *,
    scanned: dict[str, dict[str, Any]],
    existing_blobs: set[str],
    previous_refs: dict[str, Any],
    journal: PhotoExportJournal,
    file_id: str,
    page_name: str,
    overwrite: bool,
    run_mode: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    selected: dict[str, dict[str, Any]] = {}
    stats = {
        "already_successful": 0,
        "already_missed": 0,
        "already_completed_page": 0,
        "up_to_date": 0,
    }
    normalized_run_mode = normalize_run_mode(run_mode)

    if normalized_run_mode == STANDARD_RUN_MODE and journal.page_is_completed(file_id, page_name):
        stats["already_completed_page"] = len(scanned)
        return selected, stats

    for node_id, info in scanned.items():
        blob_name = normalize_blob_name(str(info["blob_name"]))
        image_ref = info.get("image_ref")
        if normalized_run_mode == RETRY_MISSED_RUN_MODE:
            if journal.is_missed(blob_name):
                selected[node_id] = dict(info)
            continue

        if journal.is_successful(blob_name):
            stats["already_successful"] += 1
            continue
        if journal.is_missed(blob_name):
            stats["already_missed"] += 1
            continue

        # Standard mode is resumable by default. Existing blobs whose cached imageRef
        # still matches the current Figma imageRef are treated as already satisfied,
        # which lets a restarted run continue from the current Azure/cache state.
        needs_upload = blob_name not in existing_blobs or image_ref != previous_refs.get(node_id)
        if needs_upload:
            selected[node_id] = dict(info)
        else:
            stats["up_to_date"] += 1

    return selected, stats


def fetch_figma_image_url_with_retry(
    *,
    file_id: str,
    node_id: str,
    canvas_height: float,
    figma_token: str,
    calculate_scale: ScaleCalculator,
    log: PhotoLogFn = print,
    attempts: int = 3,
    timeout_seconds: int = 30,
    image_format: str = "png",
) -> tuple[str | None, str]:
    last_detail = "No image URL returned."
    for attempt in range(1, attempts + 1):
        try:
            scale = calculate_scale(canvas_height)
            response = requests.get(
                f"https://api.figma.com/v1/images/{file_id}",
                headers={"X-Figma-Token": figma_token},
                params={"ids": node_id, "format": image_format, "scale": scale},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            url = response.json().get("images", {}).get(node_id)
            if url:
                return url, ""
            last_detail = f"Figma response did not include an image URL for node {node_id}."
        except Exception as exc:  # pragma: no cover - exercised via caller tests/mocks
            last_detail = format_exception(exc)
            log(f"⚠️ URL fetch retry {attempt}/{attempts} for {node_id}: {last_detail}")
        if attempt < attempts:
            time.sleep(min(2 * attempt, 5))
    return None, last_detail


async def fetch_image_bytes_with_retry(
    *,
    url: str,
    log: PhotoLogFn = print,
    attempts: int = 3,
    timeout_seconds: int = 30,
) -> tuple[bytes | None, str]:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    last_detail = "No image bytes returned."
    for attempt in range(1, attempts + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read(), ""
                    last_detail = f"HTTP {response.status}"
        except Exception as exc:  # pragma: no cover - exercised via caller tests/mocks
            last_detail = format_exception(exc)
            log(f"⚠️ Image fetch retry {attempt}/{attempts} for {url}: {last_detail}")
            fallback_bytes, fallback_detail = await fetch_image_bytes_with_requests_fallback(
                url=url,
                timeout_seconds=max(timeout_seconds, 60),
            )
            if fallback_bytes is not None:
                log(f"↪️ Requests fallback succeeded for {url}")
                return fallback_bytes, ""
            if fallback_detail:
                last_detail = fallback_detail
                log(f"⚠️ Requests fallback failed for {url}: {fallback_detail}")
        if attempt < attempts:
            await asyncio.sleep(min(2 * attempt, 5))
    return None, last_detail


def _requests_fetch_image_bytes(url: str, timeout_seconds: int) -> tuple[bytes | None, str]:
    try:
        response = requests.get(url, timeout=(15, timeout_seconds))
        response.raise_for_status()
        return response.content, ""
    except Exception as exc:
        return None, format_exception(exc)


async def fetch_image_bytes_with_requests_fallback(
    *,
    url: str,
    timeout_seconds: int = 60,
) -> tuple[bytes | None, str]:
    return await asyncio.to_thread(_requests_fetch_image_bytes, url, timeout_seconds)


async def upload_scanned_page(
    *,
    stage_name: str,
    journal: PhotoExportJournal,
    file_id: str,
    page_name: str,
    scanned: dict[str, dict[str, Any]],
    existing_blobs: set[str],
    cache_path: str | Path,
    overwrite: bool,
    run_mode: str,
    figma_token: str,
    calculate_scale: ScaleCalculator,
    convert_to_webp: ConvertToWebpFn,
    upload_blob: UploadBlobFn,
    log: PhotoLogFn = print,
) -> dict[str, Any]:
    previous_refs = load_json_file(cache_path, {})
    selected, selection_stats = select_scanned_nodes(
        scanned=scanned,
        existing_blobs=existing_blobs,
        previous_refs=previous_refs,
        journal=journal,
        file_id=file_id,
        page_name=page_name,
        overwrite=overwrite,
        run_mode=run_mode,
    )

    total_scanned = len(scanned)
    log(
        "🧮 "
        f"{total_scanned} total | {len(selected)} to upload | "
        f"resume-skip(success={selection_stats['already_successful']}, "
        f"missed={selection_stats['already_missed']}, "
        f"completed_page={selection_stats['already_completed_page']}, "
        f"up_to_date={selection_stats['up_to_date']})"
    )

    if not selected:
        summary = {
            "status": "ok",
            "page_name": page_name,
            "scanned": total_scanned,
            "selected": 0,
            "uploaded": 0,
            "skipped_no_url": 0,
            "skipped_no_bytes": 0,
            "upload_errors": 0,
            "missing_height": 0,
            "selection": selection_stats,
        }
        if normalize_run_mode(run_mode) == STANDARD_RUN_MODE and not journal.page_is_completed(file_id, page_name):
            journal.record_page_completed(file_id=file_id, page_name=page_name, summary=summary)
        return summary

    uploaded = 0
    skipped_no_height = 0
    skipped_no_url = 0
    skipped_no_bytes = 0
    upload_errors = 0

    for index, (node_id, info) in enumerate(selected.items(), 1):
        blob_name = normalize_blob_name(str(info["blob_name"]))
        canvas_height = float(info.get("canvas_height", 0) or 0)
        if not canvas_height:
            skipped_no_height += 1

        url, url_detail = fetch_figma_image_url_with_retry(
            file_id=file_id,
            node_id=node_id,
            canvas_height=canvas_height,
            figma_token=figma_token,
            calculate_scale=calculate_scale,
            log=log,
        )
        if not url:
            skipped_no_url += 1
            journal.record_miss(
                blob_name=blob_name,
                node_id=node_id,
                file_id=file_id,
                page_name=page_name,
                reason="no_url",
                detail=url_detail,
            )
            log(f"❌ [{index}] Missed {blob_name} | no_url | {url_detail}")
            continue

        image_bytes, bytes_detail = await fetch_image_bytes_with_retry(url=url, log=log)
        if not image_bytes:
            skipped_no_bytes += 1
            journal.record_miss(
                blob_name=blob_name,
                node_id=node_id,
                file_id=file_id,
                page_name=page_name,
                reason="no_bytes",
                detail=bytes_detail,
                url=url,
            )
            log(f"❌ [{index}] Missed {blob_name} | no_bytes | {bytes_detail}")
            continue

        webp = convert_to_webp(image_bytes)
        log(f"✅ [{index}] Uploading {blob_name}")
        try:
            await upload_blob(blob_name, webp)
        except Exception as exc:  # pragma: no cover - depends on external service
            upload_errors += 1
            detail = format_exception(exc)
            journal.record_miss(
                blob_name=blob_name,
                node_id=node_id,
                file_id=file_id,
                page_name=page_name,
                reason="upload_error",
                detail=detail,
                url=url,
            )
            log(f"❌ [{index}] Upload failed {blob_name} | {detail}")
            continue

        image_ref = info.get("image_ref")
        if image_ref is not None:
            previous_refs[node_id] = image_ref
            save_json_file(cache_path, previous_refs)

        journal.record_success(
            blob_name=blob_name,
            node_id=node_id,
            file_id=file_id,
            page_name=page_name,
            url=url,
        )
        existing_blobs.add(blob_name)
        uploaded += 1

    summary = {
        "status": "ok",
        "page_name": page_name,
        "scanned": total_scanned,
        "selected": len(selected),
        "uploaded": uploaded,
        "skipped_no_url": skipped_no_url,
        "skipped_no_bytes": skipped_no_bytes,
        "upload_errors": upload_errors,
        "missing_height": skipped_no_height,
        "selection": selection_stats,
    }
    if normalize_run_mode(run_mode) == STANDARD_RUN_MODE:
        journal.record_page_completed(file_id=file_id, page_name=page_name, summary=summary)
    log(
        f"📊 Done | Uploaded: {uploaded} | "
        f"Skipped(no_url): {skipped_no_url} | "
        f"Skipped(no_bytes): {skipped_no_bytes} | "
        f"UploadErrors: {upload_errors} | "
        f"MissingHeight: {skipped_no_height}"
    )
    if skipped_no_url or skipped_no_bytes or upload_errors:
        log(f"📝 Missed items logged to {journal.missed_csv_path}")
    return summary


async def run_image_upload_page(
    *,
    journal: PhotoExportJournal,
    file_id: str,
    figma_pages: list[dict[str, Any]],
    page_name: str,
    existing_blobs: set[str],
    cache_path: str | Path,
    overwrite: bool,
    run_mode: str,
    figma_token: str,
    calculate_scale: ScaleCalculator,
    scan_page: ScanPageFn,
    convert_to_webp: ConvertToWebpFn,
    upload_blob: UploadBlobFn,
    log: PhotoLogFn = print,
) -> dict[str, Any]:
    page = next((candidate for candidate in figma_pages if candidate.get("name") == page_name), None)
    if not page:
        log(f"⚠️ Page not found: {page_name}")
        return {"status": "warning", "page_name": page_name, "reason": "page_not_found"}

    log(f"\n📄 Processing page: {page_name}")
    scanned = scan_page(page)
    if not scanned:
        log(f"ℹ️ {page_name}: no exportable images found")
        return {"status": "ok", "page_name": page_name, "scanned": 0, "selected": 0}

    normalized_scanned = {
        node_id: {
            **info,
            "blob_name": normalize_blob_name(str(info["blob_name"])),
        }
        for node_id, info in scanned.items()
    }
    return await upload_scanned_page(
        stage_name="image_upload",
        journal=journal,
        file_id=file_id,
        page_name=page_name,
        scanned=normalized_scanned,
        existing_blobs=existing_blobs,
        cache_path=cache_path,
        overwrite=overwrite,
        run_mode=run_mode,
        figma_token=figma_token,
        calculate_scale=calculate_scale,
        convert_to_webp=convert_to_webp,
        upload_blob=upload_blob,
        log=log,
    )


def _walk_collect(node: dict[str, Any], out: list[dict[str, Any]]) -> None:
    out.append(node)
    for child in node.get("children", []) or []:
        _walk_collect(child, out)


def scan_infographic_page(page: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], int]:
    nodes: list[dict[str, Any]] = []
    _walk_collect(page, nodes)
    page_folder = page.get("name", "").replace(" ", "_").strip()
    scanned: dict[str, dict[str, Any]] = {}
    skipped = 0

    for node in nodes:
        if node.get("type") != "FRAME" or node.get("name") != "infographic":
            continue
        child_frames = [
            child for child in (node.get("children", []) or [])
            if child.get("type") == "FRAME"
        ]
        if len(child_frames) != 1:
            skipped += 1
            continue
        design = child_frames[0]
        node_id = str(design["id"])
        scanned[node_id] = {
            "node_id": node_id,
            "blob_name": f"Modules/{page_folder}/{node_id.replace(':', '_')}.webp",
            "image_ref": None,
            "canvas_height": float(
                ((design.get("absoluteBoundingBox") or {}).get("height")) or 800.0
            ),
            "type": "infographic",
        }
    return scanned, skipped


async def run_infographic_export_page(
    *,
    journal: PhotoExportJournal,
    file_id: str,
    figma_pages: list[dict[str, Any]],
    page_name: str,
    existing_blobs: set[str],
    cache_path: str | Path,
    overwrite: bool,
    run_mode: str,
    figma_token: str,
    calculate_scale: ScaleCalculator,
    convert_to_webp: ConvertToWebpFn,
    upload_blob: UploadBlobFn,
    log: PhotoLogFn = print,
) -> dict[str, Any]:
    page = next(
        (
            candidate
            for candidate in figma_pages
            if candidate.get("name") == page_name and candidate.get("type") in ("CANVAS", "PAGE", "FRAME")
        ),
        None,
    )
    if not page:
        log(f"⚠️ Page not found: {page_name}")
        return {"status": "warning", "page_name": page_name, "reason": "page_not_found"}

    log(f"\n📄 Processing infographics: {page_name}")
    scanned, skipped_count = scan_infographic_page(page)
    if skipped_count:
        log(
            f"⏭️ {page_name}: skipped {skipped_count} infographic container(s) "
            "because they did not contain exactly one child frame"
        )
    if not scanned:
        log(f"ℹ️ {page_name}: no infographics found")
        return {"status": "ok", "page_name": page_name, "scanned": 0, "selected": 0}

    log(f"🖼️ {page_name}: {len(scanned)} infographic frame(s) ready for export")
    return await upload_scanned_page(
        stage_name="infographic_export",
        journal=journal,
        file_id=file_id,
        page_name=page_name,
        scanned=scanned,
        existing_blobs=existing_blobs,
        cache_path=cache_path,
        overwrite=overwrite,
        run_mode=run_mode,
        figma_token=figma_token,
        calculate_scale=calculate_scale,
        convert_to_webp=convert_to_webp,
        upload_blob=upload_blob,
        log=log,
    )


def print_journal_summary(journal: PhotoExportJournal, log: PhotoLogFn = print) -> None:
    journal.flush_snapshots(force=True)
    log(
        f"🧾 {journal.stage_name}: "
        f"{len(journal.successful_blobs)} successful, "
        f"{len(journal.missed_blobs)} unresolved misses, "
        f"{len(journal.completed_pages)} completed page(s)"
    )
    log(f"🧾 Summary: {journal.summary_path}")
    log(f"🧾 Missed CSV: {journal.missed_csv_path}")
