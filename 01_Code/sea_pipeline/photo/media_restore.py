"""Restore a single optimized blob from its recorded original (explicit CLI action)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import unquote

from sea_pipeline.photo.media_optimization import MANIFEST_NAME, ORIGINAL_PREFIX, build_container, _error_detail


def restore_original(container, blob_name: str, *, update_manifest: bool = True) -> dict[str, str]:
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceNotFoundError
    from azure.storage.blob import ContentSettings

    target = container.get_blob_client(blob_name)
    props = target.get_blob_properties()
    backup_name = unquote((props.metadata or {}).get("sea_media_original", ""))
    if not backup_name.startswith(ORIGINAL_PREFIX):
        raise ValueError("This asset has no media optimizer original backup.")
    backup = container.get_blob_client(backup_name)
    original = backup.get_blob_properties()
    target.upload_blob_from_url(backup.url, overwrite=True,
        etag=props.etag, match_condition=MatchConditions.IfNotModified,
        source_etag=original.etag, source_match_condition=MatchConditions.IfNotModified,
        content_settings=original.content_settings, metadata=original.metadata or {})

    if not update_manifest:
        return {"blob": blob_name, "status": "restored", "backup": backup_name}

    # Drop optimized routes for this asset. An ETag guards against an active run.
    manifest_blob = container.get_blob_client(MANIFEST_NAME)
    try:
        download = manifest_blob.download_blob()
        manifest = json.loads(download.readall())
    except ResourceNotFoundError:
        return {"blob": blob_name, "status": "restored", "backup": backup_name}
    for section in ("images", "videos"):
        manifest.get(section, {}).pop(blob_name, None)
    manifest_blob.upload_blob(json.dumps(manifest).encode(), overwrite=True,
        etag=download.properties.etag, match_condition=MatchConditions.IfNotModified,
        content_settings=ContentSettings(content_type="application/json", cache_control="public, max-age=300"))
    return {"blob": blob_name, "status": "restored", "backup": backup_name}


def main():
    from dotenv import load_dotenv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blob_name", help="Container-relative path, e.g. HeaderImages/Modules/module1.webp")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[3] / "01_Code" / ".env", override=True)
    try:
        result = restore_original(build_container(os.getenv("SAS_URL"), os.getenv("AZURE_STORAGE_CONTAINER_URL")), args.blob_name)
        print(json.dumps(result))
    except Exception as exc:
        raise SystemExit(str(exc) if isinstance(exc, ValueError) else _error_detail(exc)) from None


if __name__ == "__main__":
    main()
