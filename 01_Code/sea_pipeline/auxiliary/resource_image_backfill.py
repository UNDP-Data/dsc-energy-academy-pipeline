from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from PIL import Image


RESOURCE_URL_MARKER = "/images/Resources/"


class BlobContainerProtocol(Protocol):
    container_name: str

    def blob_exists(self, blob_name: str) -> bool: ...

    def download_blob_bytes(self, blob_name: str) -> bytes: ...

    def upload_blob_bytes(
        self,
        blob_name: str,
        data: bytes,
        *,
        content_type: str,
        overwrite: bool,
    ) -> None: ...


@dataclass
class ResourceImageBackfillChange:
    resource_url: str
    webp_blob_name: str
    png_blob_name: str
    status: str
    message: str = ""


class AzureBlobContainerAdapter:
    def __init__(self, sas_url: str) -> None:
        if not sas_url:
            raise ValueError("SAS_URL is required for resource image backfill.")
        try:
            from azure.storage.blob import ContainerClient, ContentSettings
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "azure-storage-blob is required for resource image backfill."
            ) from exc

        self._content_settings_cls = ContentSettings
        self._container_client = ContainerClient.from_container_url(sas_url)
        parsed = urlparse(sas_url)
        self.container_name = parsed.path.strip("/").split("/")[-1]
        if not self.container_name:
            raise ValueError(f"Could not infer Azure container name from SAS_URL: {sas_url}")

    def blob_exists(self, blob_name: str) -> bool:
        return self._container_client.get_blob_client(blob_name).exists()

    def download_blob_bytes(self, blob_name: str) -> bytes:
        return self._container_client.get_blob_client(blob_name).download_blob().readall()

    def upload_blob_bytes(
        self,
        blob_name: str,
        data: bytes,
        *,
        content_type: str,
        overwrite: bool,
    ) -> None:
        self._container_client.get_blob_client(blob_name).upload_blob(
            data,
            overwrite=overwrite,
            content_settings=self._content_settings_cls(content_type=content_type),
        )


def iter_resource_image_urls(
    lesson_root: str | Path,
    *,
    lesson_glob: str = "Module_*/*.json",
) -> list[str]:
    root = Path(lesson_root)
    resource_urls: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            src = node.get("src")
            if isinstance(src, str) and RESOURCE_URL_MARKER in src:
                resource_urls.add(src)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for lesson_path in sorted(root.glob(lesson_glob)):
        if lesson_path.name == "module_structure.json":
            continue
        walk(json.loads(lesson_path.read_text(encoding="utf-8")))

    return sorted(resource_urls)


def resource_blob_name_from_url(resource_url: str, container_name: str) -> str:
    parsed = urlparse(resource_url)
    path = parsed.path.lstrip("/")
    container_prefix = f"{container_name}/"
    if not path.startswith(container_prefix):
        raise ValueError(
            f"Resource URL does not point into container '{container_name}': {resource_url}"
        )
    return path[len(container_prefix) :]


def sibling_png_blob_name(webp_blob_name: str) -> str:
    blob_path = Path(webp_blob_name)
    return str(blob_path.with_suffix(".png"))


def convert_png_bytes_to_webp(png_bytes: bytes) -> bytes:
    output = BytesIO()
    with Image.open(BytesIO(png_bytes)) as image:
        if image.mode not in {"RGB", "RGBA"}:
            has_alpha = "A" in image.getbands() or image.mode in {"LA", "PA"} or "transparency" in image.info
            image = image.convert("RGBA" if has_alpha else "RGB")
        image.save(output, format="WEBP", lossless=True)
    return output.getvalue()


def backfill_resource_webp_images(
    lesson_root: str | Path,
    *,
    sas_url: str | None = None,
    lesson_glob: str = "Module_*/*.json",
    limit: int | None = None,
    overwrite: bool = True,
    container: BlobContainerProtocol | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    blob_container = container or AzureBlobContainerAdapter(sas_url or "")
    resource_urls = iter_resource_image_urls(lesson_root, lesson_glob=lesson_glob)
    if limit is not None:
        resource_urls = resource_urls[:limit]

    changes: list[ResourceImageBackfillChange] = []
    total_resources = len(resource_urls)
    for idx, resource_url in enumerate(resource_urls, start=1):
        try:
            webp_blob_name = resource_blob_name_from_url(resource_url, blob_container.container_name)
            png_blob_name = sibling_png_blob_name(webp_blob_name)

            if blob_container.blob_exists(webp_blob_name):
                if log:
                    log(f"[{idx}/{total_resources}] Existing WebP: {webp_blob_name}")
                changes.append(
                    ResourceImageBackfillChange(
                        resource_url=resource_url,
                        webp_blob_name=webp_blob_name,
                        png_blob_name=png_blob_name,
                        status="existing_webp",
                    )
                )
                continue

            if not blob_container.blob_exists(png_blob_name):
                if log:
                    log(f"[{idx}/{total_resources}] Missing both: {webp_blob_name} | fallback PNG: {png_blob_name}")
                changes.append(
                    ResourceImageBackfillChange(
                        resource_url=resource_url,
                        webp_blob_name=webp_blob_name,
                        png_blob_name=png_blob_name,
                        status="missing_both",
                    )
                )
                continue

            png_bytes = blob_container.download_blob_bytes(png_blob_name)
            webp_bytes = convert_png_bytes_to_webp(png_bytes)
            blob_container.upload_blob_bytes(
                webp_blob_name,
                webp_bytes,
                content_type="image/webp",
                overwrite=overwrite,
            )
            if log:
                log(f"[{idx}/{total_resources}] Converted PNG to WebP: {png_blob_name} -> {webp_blob_name}")
            changes.append(
                ResourceImageBackfillChange(
                    resource_url=resource_url,
                    webp_blob_name=webp_blob_name,
                    png_blob_name=png_blob_name,
                    status="converted_from_png",
                )
            )
        except Exception as exc:
            webp_blob_name = ""
            png_blob_name = ""
            try:
                webp_blob_name = resource_blob_name_from_url(resource_url, blob_container.container_name)
                png_blob_name = sibling_png_blob_name(webp_blob_name)
            except Exception:
                pass
            if log:
                log(f"[{idx}/{total_resources}] Error: {resource_url} | {exc}")
            changes.append(
                ResourceImageBackfillChange(
                    resource_url=resource_url,
                    webp_blob_name=webp_blob_name,
                    png_blob_name=png_blob_name,
                    status="error",
                    message=str(exc),
                )
            )

    return {
        "status": "ok",
        "lesson_glob": lesson_glob,
        "limit": limit,
        "scanned_resources": len(resource_urls),
        "existing_webp": sum(change.status == "existing_webp" for change in changes),
        "converted_from_png": sum(change.status == "converted_from_png" for change in changes),
        "missing_both": sum(change.status == "missing_both" for change in changes),
        "errors": sum(change.status == "error" for change in changes),
        "changes": [asdict(change) for change in changes],
    }
