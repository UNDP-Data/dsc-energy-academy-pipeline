from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from sea_pipeline.shared.redaction import redact_text

from sea_pipeline.auxiliary.resource_image_backfill import (
    AzureBlobContainerAdapter,
    resource_blob_name_from_url,
)


@dataclass(frozen=True)
class ResourceBlobCheckResult:
    status: str
    exists: bool
    blob_name: str = ""
    message: str = ""


ResourceBlobChecker = Callable[[str], ResourceBlobCheckResult]


def build_resource_blob_checker(sas_url: str) -> ResourceBlobChecker:
    container = AzureBlobContainerAdapter(sas_url)
    cache: dict[str, ResourceBlobCheckResult] = {}

    def check(resource_url: str) -> ResourceBlobCheckResult:
        if resource_url in cache:
            return cache[resource_url]
        try:
            blob_name = resource_blob_name_from_url(resource_url, container.container_name)
            exists = container.blob_exists(blob_name)
            result = ResourceBlobCheckResult(
                status="exists" if exists else "missing",
                exists=exists,
                blob_name=blob_name,
                message="" if exists else f"Blob not found: {blob_name}",
            )
        except Exception as exc:  # noqa: BLE001 - review output should capture the failing URL.
            result = ResourceBlobCheckResult(
                status="error",
                exists=False,
                message=redact_text(f"{type(exc).__name__}: {exc}", (sas_url,)),
            )
        cache[resource_url] = result
        return result

    return check
