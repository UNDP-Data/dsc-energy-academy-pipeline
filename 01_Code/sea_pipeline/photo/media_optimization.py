"""Resumable Azure media optimization with originals and immutable image variants.

Run after Figma exports. Existing JSON URLs remain valid; the frontend uses the
published manifest to choose smaller images. No Figma or translation calls occur.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import mimetypes
import os
import shutil
import struct
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit

from PIL import Image, ImageOps

VERSION = "1"
VARIANT_PREFIX = "media-optimized/"
ORIGINAL_PREFIX = "media-originals/"
MANIFEST_NAME = VARIANT_PREFIX + "manifest.json"
RASTER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PHOTO_TEMPLATES = {
    "photo_horizontal", "photo_vertical", "photo_full_height", "lesson_cover",
    "lesson_part_cover", "lesson_subpart_cover", "chapter_cover", "module_cover",
    "case_study_cover", "learning_objectives", "key_takeaways", "connection_next",
}
GRAPHIC_TEMPLATES = {"infographic", "image_hotspot", "key_resources", "chart"}


@dataclass(frozen=True)
class MediaOptions:
    scope: str = "ui"
    widths: tuple[int, ...] = (320, 640, 960, 1440, 1920)
    quality: int = 82
    photo_max_edge: int = 1920
    optimize_originals: bool = True
    video_faststart: bool = True
    workers: int = 12
    limit: int | None = None
    prefix: str = ""
    max_image_bytes: int = 100 * 1024 * 1024
    max_video_bytes: int = 2 * 1024 * 1024 * 1024

    def __post_init__(self):
        if self.scope not in {"ui", "all"}:
            raise ValueError("Media scope must be 'ui' or 'all'.")
        if not self.widths or any(w <= 0 for w in self.widths):
            raise ValueError("Media widths must be positive.")
        if not 1 <= self.quality <= 100 or self.photo_max_edge <= 0:
            raise ValueError("Invalid image quality or maximum edge.")
        if self.limit is not None and self.limit <= 0:
            raise ValueError("Media limit must be positive or None.")
        if not 1 <= self.workers <= 16:
            raise ValueError("Use between 1 and 16 media workers.")

    def recipe(self, kind: str) -> str:
        settings = asdict(self)
        for key in ("limit", "prefix", "max_image_bytes", "max_video_bytes", "workers", "scope"):
            settings.pop(key)
        return hashlib.sha256(json.dumps([VERSION, kind, settings], sort_keys=True).encode()).hexdigest()[:24]


def blob_name_from_url(url: str, container_url: str) -> str | None:
    source, container = urlsplit(url), urlsplit(container_url)
    prefix = container.path.rstrip("/") + "/"
    if source.scheme != "https" or source.netloc != container.netloc or not source.path.startswith(prefix):
        return None
    return unquote(source.path[len(prefix):])


def image_roles(lesson_root: Path, container_url: str) -> dict[str, str]:
    """Unknown assets stay lossless; any text-bearing use overrides a photo use."""
    roles: dict[str, str] = {}

    def walk(node: Any, template: str = "") -> None:
        if isinstance(node, dict):
            template = str(node.get("template_id", template)).lower().replace("-", "_")
            for key, value in node.items():
                if key in {"src", "poster"} and isinstance(value, str):
                    name = blob_name_from_url(value, container_url)
                    if name:
                        if template in GRAPHIC_TEMPLATES:
                            roles[name] = "graphic"
                        elif (template in PHOTO_TEMPLATES or key == "poster") and roles.get(name) != "graphic":
                            roles[name] = "photo"
                else:
                    walk(value, template)
        elif isinstance(node, list):
            for value in node:
                walk(value, template)

    for path in sorted(lesson_root.glob("**/*.json")):
        # Structure uses cover photos without a template_id.
        if path.name != "module_structure.json":
            walk(json.loads(path.read_text(encoding="utf-8")))
    return roles


def media_kind(name: str, roles: dict[str, str]) -> str:
    if name in roles:
        return roles[name]
    if name.startswith(("HeaderImages/", "Lessons/image/", "Photos/")) or "/Photos/" in name:
        return "photo"
    return "graphic"


def ui_image_names(lesson_root: Path, container_url: str) -> set[str]:
    """Only images/frames referenced by the navigation/module structure are UI assets."""
    names: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            src = value.get("src")
            if isinstance(src, str):
                name = blob_name_from_url(src, container_url)
                if name and Path(name).suffix.lower() in RASTER_EXTENSIONS:
                    names.add(name)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for path in sorted(lesson_root.glob("**/module_structure.json")):
        walk(json.loads(path.read_text(encoding="utf-8")))
    if not names:
        raise ValueError("No UI images found in module_structure.json; refusing to expand to content media.")
    return names


def encode_image(image: Image.Image, fmt: str, *, quality: int, lossless: bool) -> bytes:
    output = BytesIO()
    profile = {"icc_profile": image.info["icc_profile"]} if image.info.get("icc_profile") else {}
    if fmt == "JPEG":
        image.convert("RGB").save(output, fmt, quality=quality, optimize=True, progressive=True, **profile)
    elif fmt == "PNG":
        image.save(output, fmt, optimize=True, **profile)
    else:
        image.save(output, "WEBP", quality=quality, lossless=lossless, method=6, **profile)
    return output.getvalue()


def prepare_image(data: bytes, name: str, kind: str, options: MediaOptions) -> dict[str, Any]:
    with Image.open(BytesIO(data)) as source:
        if getattr(source, "is_animated", False):
            return {"skip": "animated image preserved"}
        image = ImageOps.exif_transpose(source).convert(
            "RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB"
        )
    # Preserve diagrams, report covers and unknown assets at full resolution.
    lossless = kind != "photo"
    original = image.copy()
    if not lossless:
        original.thumbnail((options.photo_max_edge, options.photo_max_edge), Image.Resampling.LANCZOS)
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[Path(name).suffix.lower()]
    candidate = data if fmt == "JPEG" and lossless else encode_image(original, fmt, quality=options.quality, lossless=lossless)
    replacement = candidate if options.optimize_originals and len(candidate) < len(data) * 0.95 else data
    variants = []
    # Include native width for narrow originals, and never upscale.
    for width in sorted({min(width, image.width) for width in options.widths}):
        height = max(1, round(image.height * width / image.width))
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        encoded = encode_image(resized, "WEBP", quality=options.quality, lossless=lossless)
        if len(encoded) < len(replacement):
            variants.append({"width": width, "height": height, "data": encoded})
    displayed = image if replacement == data else original
    return {"original": replacement, "variants": variants, "width": displayed.width, "height": displayed.height}


def mp4_has_faststart(path: Path) -> bool:
    """Inspect top-level MP4 boxes without loading video payloads into memory."""
    length = path.stat().st_size
    with path.open("rb") as stream:
        while stream.tell() + 8 <= length:
            start = stream.tell()
            size, kind = struct.unpack(">I4s", stream.read(8))
            header_size = 8
            if size == 1:
                header = stream.read(8)
                if len(header) != 8:
                    return False
                size = struct.unpack(">Q", header)[0]
                header_size = 16
            elif size == 0:
                size = length - start
            if size < header_size or start + size > length:
                return False
            if kind == b"moov":
                return True
            if kind == b"mdat":
                return False
            stream.seek(start + size)
    return False


def faststart_video(source: Path, destination: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for MP4 fast-start optimization.")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source),
         "-map", "0", "-c", "copy", "-movflags", "+faststart", str(destination)],
        check=True, capture_output=True, timeout=1800,
    )
    if not mp4_has_faststart(destination):
        raise RuntimeError("MP4 output failed fast-start verification.")


def remote_mp4_has_faststart(client, props) -> bool:
    """Read box headers only, avoiding multi-GB downloads of ready-to-stream video."""
    from azure.core import MatchConditions
    offset = 0
    for _ in range(64):
        if offset + 8 > props.size:
            return False
        data = client.download_blob(offset=offset, length=min(16, props.size - offset),
                                    etag=props.etag, match_condition=MatchConditions.IfNotModified).readall()
        size, kind = struct.unpack(">I4s", data[:8])
        if size == 1:
            size = struct.unpack(">Q", data[8:16])[0]
        elif size == 0:
            size = props.size - offset
        if size < 8 or offset + size > props.size:
            return False
        if kind == b"moov":
            return True
        if kind == b"mdat":
            return False
        offset += size
    return False


def build_container(sas_url: str | None = None, container_url: str | None = None):
    from azure.storage.blob import ContainerClient
    transfer_options = dict(connection_timeout=15, read_timeout=60, retry_total=3,
                            max_single_get_size=4 * 1024 * 1024, max_chunk_get_size=4 * 1024 * 1024,
                            max_single_put_size=4 * 1024 * 1024, max_block_size=4 * 1024 * 1024)
    if sas_url:
        expiry = parse_qs(urlsplit(sas_url).query).get("se", [None])[0]
        if expiry and datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            raise ValueError("SAS_URL has expired. Update 01_Code/.env before uploading media.")
        return ContainerClient.from_container_url(sas_url, **transfer_options)
    if not container_url:
        raise ValueError("Provide SAS_URL, or AZURE_STORAGE_CONTAINER_URL with an Azure CLI login.")
    from azure.identity import AzureCliCredential
    return ContainerClient.from_container_url(container_url, credential=AzureCliCredential(), **transfer_options)


def _error_detail(exc: Exception) -> str:
    # SDK messages can include signed request URLs. Report only safe diagnostics.
    return f"{type(exc).__name__} (status={getattr(exc, 'status_code', None)}, code={getattr(exc, 'error_code', None)})"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def optimize_container_media(
    container, *, lesson_root: Path, report_dir: Path,
    options: MediaOptions = MediaOptions(), log: Callable[[str], None] = print,
) -> dict[str, Any]:
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    from azure.storage.blob import ContentSettings

    base_url = container.url.split("?", 1)[0].rstrip("/")
    roles = image_roles(lesson_root, base_url)
    ui_names = ui_image_names(lesson_root, base_url) if options.scope == "ui" else None
    log("Listing Azure media and loading optimization manifest...")
    inventory = {b.name: b for b in container.list_blobs()}
    manifest_blob = container.get_blob_client(MANIFEST_NAME)
    manifest_etag = None
    try:
        download = manifest_blob.download_blob()
        manifest = json.loads(download.readall())
        manifest_etag = download.properties.etag
        if manifest.get("version") != VERSION or manifest.get("container_url") != base_url:
            raise ValueError("Incompatible media manifest; refusing to replace it.")
    except ResourceNotFoundError:
        manifest = {"version": VERSION, "container_url": base_url, "images": {}, "videos": {}}

    checkpoint = report_dir / "manifest.json"
    if checkpoint.exists():
        local = json.loads(checkpoint.read_text(encoding="utf-8"))
        if local.get("version") == VERSION and local.get("container_url") == base_url:
            for section in ("images", "videos"):
                for name, entry in local.get(section, {}).items():
                    # Recover completed writes from an interrupted, unpublished batch.
                    if (name in inventory and entry.get("etag") == inventory[name].etag
                            and all(v["blob"] in inventory for v in entry.get("variants", []))):
                        manifest[section][name] = entry

    report_dir.mkdir(parents=True, exist_ok=True)
    state_lock = Lock()
    stop = Event()
    totals = {"processed": 0, "resumed": 0, "optimized": 0, "skipped": 0, "errors": 0,
              "bytes_before": 0, "bytes_after": 0, "variant_bytes": 0}

    def publish() -> None:
        nonlocal manifest_etag
        data = json.dumps(manifest, separators=(",", ":")).encode()
        kwargs = {"overwrite": False} if manifest_etag is None else {
            "overwrite": True, "etag": manifest_etag, "match_condition": MatchConditions.IfNotModified}
        result = manifest_blob.upload_blob(data, content_settings=ContentSettings(
            content_type="application/json", cache_control="public, max-age=300"), **kwargs)
        manifest_etag = result["etag"]
        _atomic_json(report_dir / "manifest.json", manifest)

    def backup(blob_name: str, original: bytes | Path, props) -> str:
        digest = hashlib.sha256()
        if isinstance(original, Path):
            with original.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(original)
        backup_name = f"{ORIGINAL_PREFIX}{digest.hexdigest()}/{blob_name}"
        if backup_name not in inventory:
            target = container.get_blob_client(backup_name)
            try:
                # Copy inside Azure; uploading originals back from the laptop
                # would needlessly transfer the entire video library twice.
                target.upload_blob_from_url(container.get_blob_client(blob_name).url,
                    overwrite=False, source_etag=props.etag,
                    source_match_condition=MatchConditions.IfNotModified,
                    content_settings=props.content_settings, metadata=props.metadata)
            except ResourceExistsError:
                pass
            inventory[backup_name] = True
        return backup_name

    names = sorted(name for name in inventory if name.startswith(options.prefix)
                   and not name.startswith((VARIANT_PREFIX, ORIGINAL_PREFIX))
                   and (ui_names is None or name in ui_names)
                   and Path(name).suffix.lower() in (RASTER_EXTENSIONS | {".mp4", ".svg", ".gif"}))
    missing_ui = sorted(ui_names - inventory.keys()) if ui_names is not None else []
    if ui_names is not None:
        _atomic_json(report_dir / "missing_ui_images.json", missing_ui)
    if missing_ui:
        log(f"{len(missing_ui)} UI image references are missing from Azure; see missing_ui_images.json.")
    # Make the academy landing page the first assets updated in a limited run.
    names.sort(key=lambda name: (Path(name).suffix.lower() == ".mp4", not name.startswith("HeaderImages/"), name not in roles, name))
    if options.limit:
        names = names[:options.limit]
    log(f"{len(names)} media assets selected (scope={options.scope}); existing originals and variants are reusable.")
    report_path = report_dir / "media_optimization.csv"
    if report_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(report_path, report_dir / f"media_optimization_{stamp}.csv")
    _atomic_json(report_dir / "summary.json", {"stage": "media_optimization", "status": "running",
        "selected": len(names), "summary": totals, "report_path": str(report_path)})
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["blob", "status", "kind", "bytes_before", "bytes_after", "variant_bytes", "backup", "detail"])
        writer.writeheader()
        def process(item):
            index, name = item
            if stop.is_set():
                return
            log(f"[{index}/{len(names)}] Inspecting {name}")
            row = {"blob": name, "status": "ok", "kind": media_kind(name, roles), "bytes_before": inventory[name].size,
                   "bytes_after": inventory[name].size, "variant_bytes": 0, "backup": "", "detail": ""}
            extension = Path(name).suffix.lower()
            section = "videos" if extension == ".mp4" else "images"
            kind = "video" if extension == ".mp4" else row["kind"]
            recipe = options.recipe(kind)
            try:
                client = container.get_blob_client(name)
                props = client.get_blob_properties()
                previous = manifest[section].get(name, {})
                if (previous.get("etag") == props.etag and previous.get("recipe") == recipe
                        and all(v["blob"] in inventory for v in previous.get("variants", []))):
                    row["status"] = "resumed"
                elif extension in {".svg", ".gif"}:
                    row["status"], row["detail"] = "skipped", "Vector/animation preserved without rasterization."
                elif extension == ".mp4" and not options.video_faststart:
                    row["status"], row["detail"] = "skipped", "Video fast-start disabled."
                elif props.size > (options.max_video_bytes if extension == ".mp4" else options.max_image_bytes):
                    row["status"], row["detail"] = "skipped", "Exceeds configured download size limit."
                elif extension == ".mp4" and remote_mp4_has_faststart(client, props):
                    settings = copy.copy(props.content_settings)
                    settings.content_type = "video/mp4"
                    settings.cache_control = "public, max-age=86400"
                    result = client.set_http_headers(settings, etag=props.etag, match_condition=MatchConditions.IfNotModified)
                    with state_lock:
                        manifest[section][name] = {"etag": result["etag"], "recipe": recipe,
                            "kind": "video", "variants": [], "original_cache_control": props.content_settings.cache_control,
                            "original_content_type": props.content_settings.content_type}
                    row["status"], row["detail"] = "optimized", "Already fast-start; cache headers updated without downloading video."
                else:
                    with tempfile.TemporaryDirectory(prefix="sea-media-") as temp:
                        original_name = unquote((props.metadata or {}).get("sea_media_original", name))
                        original_client = container.get_blob_client(original_name)
                        condition = {"etag": props.etag, "match_condition": MatchConditions.IfNotModified} if original_name == name else {}
                        raw_path = Path(temp) / ("source" + extension)
                        with raw_path.open("wb") as stream:
                            original_client.download_blob(**condition).readinto(stream)
                        entry = {"recipe": recipe, "kind": kind, "variants": []}
                        payload: bytes | Path = raw_path
                        if extension == ".mp4":
                            if not mp4_has_faststart(raw_path):
                                payload = Path(temp) / "faststart.mp4"
                                faststart_video(raw_path, payload)
                        else:
                            raw = raw_path.read_bytes()
                            prepared = prepare_image(raw, name, kind, options)
                            if "skip" in prepared:
                                row["status"], row["detail"] = "skipped", prepared["skip"]
                            else:
                                payload = prepared["original"]
                                digest = hashlib.sha256(raw + recipe.encode()).hexdigest()[:32]
                                entry.update(width=prepared["width"], height=prepared["height"])
                                for variant in prepared["variants"]:
                                    variant_name = f"{VARIANT_PREFIX}{digest}/{variant['width']}.webp"
                                    data = variant["data"]
                                    if variant_name not in inventory:
                                        try:
                                            container.get_blob_client(variant_name).upload_blob(data, overwrite=False,
                                                content_settings=ContentSettings(content_type="image/webp", cache_control="public, max-age=31536000, immutable"))
                                        except ResourceExistsError:
                                            pass
                                        inventory[variant_name] = True
                                    entry["variants"].append({"blob": variant_name,
                                        "url": base_url + "/" + quote(variant_name, safe="/"),
                                        "width": variant["width"], "height": variant["height"], "bytes": len(data)})
                                    row["variant_bytes"] += len(data)
                        if row["status"] != "skipped":
                            # Backup exists before any in-place write, even if only headers change.
                            backup_name = original_name if original_name != name else backup(name, raw_path, props)
                            row["backup"] = backup_name
                            metadata = dict(props.metadata or {})
                            metadata.update(sea_media_original=quote(backup_name, safe="/"), sea_media_recipe=recipe)
                            settings = copy.copy(props.content_settings)
                            settings.content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
                            settings.cache_control = "public, max-age=86400"
                            settings.content_md5 = None
                            kwargs = dict(overwrite=True, etag=props.etag, match_condition=MatchConditions.IfNotModified,
                                          content_settings=settings, metadata=metadata)
                            if isinstance(payload, Path):
                                row["bytes_after"] = payload.stat().st_size
                                with payload.open("rb") as stream:
                                    result = client.upload_blob(stream, **kwargs)
                            else:
                                row["bytes_after"] = len(payload)
                                if original_name == name and payload == raw:
                                    result = client.set_http_headers(settings, etag=props.etag, match_condition=MatchConditions.IfNotModified)
                                    result = client.set_blob_metadata(metadata, etag=result["etag"], match_condition=MatchConditions.IfNotModified)
                                else:
                                    result = client.upload_blob(payload, **kwargs)
                            entry.update(etag=result["etag"], backup=backup_name)
                            with state_lock:
                                manifest[section][name] = entry
                            row["status"] = "optimized"
                with state_lock:
                    if row["status"] == "resumed":
                        totals["resumed"] += 1
                    elif row["status"] == "skipped":
                        totals["skipped"] += 1
                    else:
                        totals["optimized"] += 1
                        totals["bytes_before"] += row["bytes_before"]
                        totals["bytes_after"] += row["bytes_after"]
                        totals["variant_bytes"] += row["variant_bytes"]
            except Exception as exc:
                row["status"], row["detail"] = "error", _error_detail(exc)
                with state_lock:
                    totals["errors"] += 1
                    manifest[section].pop(name, None)
                if getattr(exc, "status_code", None) in {401, 403}:
                    stop.set()
                    with state_lock:
                        writer.writerow(row)
                        handle.flush()
                    raise RuntimeError("Azure authorization failed; refresh storage credentials and rerun. Completed assets are resumable.") from None
            with state_lock:
                writer.writerow(row)
                handle.flush()
                totals["processed"] += 1
                log(f"[{index}/{len(names)}] {row['status']}: {name} | {row['bytes_before']} -> {row['bytes_after']} bytes | {row['detail']}")
                # Persist each asset locally; publish small batches to Azure.
                _atomic_json(report_dir / "manifest.json", manifest)
                if totals["processed"] % 25 == 0:
                    publish()
                    _atomic_json(report_dir / "summary.json", {"stage": "media_optimization", "status": "running",
                        "selected": len(names), "summary": totals, "report_path": str(report_path)})
        pool = ThreadPoolExecutor(max_workers=options.workers)
        try:
            for _ in pool.map(process, enumerate(names, 1)):
                pass
        finally:
            stop.set()
            pool.shutdown(wait=True, cancel_futures=True)
        publish()
    result = {"stage": "media_optimization", "status": "warning" if totals["errors"] or missing_ui else "ok",
              "scope": options.scope, "missing_ui_images": missing_ui,
              "summary": totals, "report_path": str(report_path), "manifest_url": base_url + "/" + MANIFEST_NAME}
    _atomic_json(report_dir / "summary.json", result)
    log(f"Media optimization complete: {totals}. Report: {report_path}")
    return result


def run_media_optimization(config, *, container=None, log=print) -> dict[str, Any]:
    options = MediaOptions(**dict(config.stage_options.get("media_optimization", {})))
    if container is None:
        container = build_container(config.env.sas_url, os.getenv("AZURE_STORAGE_CONTAINER_URL"))
    return optimize_container_media(container, lesson_root=config.paths.outputs_dir / "SEA_Modules",
                                    report_dir=config.paths.outputs_dir / "Media_Optimization", options=options, log=log)


def main() -> None:
    from dotenv import load_dotenv
    from sea_pipeline.shared.config import PipelineConfig
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--scope", choices=["ui", "all"], default="ui")
    parser.add_argument("--no-video", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / "01_Code" / ".env", override=True)
    config = PipelineConfig.from_repo_root(root)
    config.stage_options["media_optimization"] = {"scope": args.scope, "limit": args.limit, "prefix": args.prefix, "video_faststart": not args.no_video}
    try:
        run_media_optimization(config)
    except Exception as exc:
        # Do not print Azure exceptions containing SAS URLs.
        message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else _error_detail(exc)
        raise SystemExit(message) from None


if __name__ == "__main__":
    main()
