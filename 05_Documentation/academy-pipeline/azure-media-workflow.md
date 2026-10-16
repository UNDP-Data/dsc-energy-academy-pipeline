# Azure Media Workflow

## Overview

Azure Blob Storage is the canonical media location used in generated Academy JSON. The pipeline reads and writes blobs using `SAS_URL`, and generated content references public URLs under:

```text
https://sehseadata.blob.core.windows.net/images/
```

The inferred Azure container name is `images` for most observed URLs.

After export, run the `media_optimization` stage in `photo-export.ipynb` to create
responsive sizes, optimize originals, set cache headers, and prepare MP4s for
streaming. See [Media optimization](media-optimization.md) for controls, frontend
integration, resumable operation, and restoring originals.

## How Images Are Identified

Generic Figma images:

- The photo export scanner walks selected Figma module pages.
- Every `RECTANGLE` with an IMAGE fill and `imageRef` is treated as an export candidate.
- Node ID is used as the stable image identifier.

Infographics:

- The scanner finds frames named `infographic`.
- It requires exactly one child frame.
- The child frame node ID is exported.

Resources:

- Resource image URLs are discovered from lesson JSON by looking for `/images/Resources/` in `src`.
- The WebP backfill step checks whether the referenced `.webp` blob exists or whether a sibling `.png` exists.

Avatar videos:

- Expected final videos use `Avatars/{language}/{module}/Videos/Lesson-{lesson_id}_{language}.mp4`.
- HeyGen intermediate videos use `AI_Avatars/Lesson-{lesson_id}_{language}_{part}.mp4`.

## imageRefs Cache

Cache path:

```text
03_Outputs/image_refs_cache.json
```

The cache stores Figma node ID to Figma `imageRef` mappings. During standard photo export:

- If a blob already exists and the cached `imageRef` matches the current Figma `imageRef`, the upload is skipped as up to date.
- If `overwrite` is true, or the blob is missing, or the `imageRef` changed, the image is selected for upload.

## Azure Blob Uploads

The photo export legacy notebook snapshot creates an async `ContainerClient` from `SAS_URL` and uploads with content type `image/webp`.

Observed upload flow:

1. List existing blob names.
2. Load `image_refs_cache.json`.
3. Scan a page for export candidates.
4. Select candidates based on overwrite, existing blobs, cache, and journal status.
5. Call Figma image URL endpoint.
6. Download image bytes from the Figma-provided URL.
7. Convert bytes to WebP.
8. Upload to Azure.
9. Update image refs cache and journal.

## Naming Conventions

Generic page image:

```text
Modules/Module_<n>/<figma_node_id_with_colon_replaced>.webp
```

Example:

```text
Modules/Module_4/8001_2050.webp
```

Resource image:

```text
Resources/Module_<n>/resource-<id>.webp
```

Avatar final video:

```text
Avatars/<language>/<module>/Videos/Lesson-<lesson_id>_<language>.mp4
```

Avatar poster:

```text
Avatars/<language>/<module>/Photos/Lesson-<lesson_id>_<language>.webp
```

Non-avatar Figma video:

```text
Videos/src/<video_name>.mp4
Videos/poster/<video_name>.png
```

## Avoiding Redundant Uploads

Mechanisms:

- Azure blob listing for existing blobs.
- Figma `imageRef` cache.
- `PhotoExportJournal` success/miss/completed-page events.
- `standard` run mode skips completed pages and already-satisfied images.
- `retry_missed` run mode selects only unresolved missed blobs.

Journal outputs:

- `03_Outputs/Photo_Export_Logs/image_upload_events.jsonl`
- `03_Outputs/Photo_Export_Logs/image_upload_summary.json`
- `03_Outputs/Photo_Export_Logs/image_upload_missed.json`
- `03_Outputs/Photo_Export_Logs/image_upload_missed.csv`
- Equivalent `infographic_export_*` files for infographics.

## Output URLs

Generated JSON stores full URLs, not only blob names.

Example:

```json
{
  "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/3605_621.webp",
  "caption": ""
}
```

DOCX exports shorten video placeholders for readability, but lesson JSON keeps full URLs.

## Known Failure Cases

- `no_url`: Figma image endpoint did not return a URL for a node.
- `no_bytes`: the Figma-provided S3 URL could not be downloaded or timed out.
- `upload_error`: Azure upload failed.
- Missing `absoluteBoundingBox.height`: scale fallback is used, but the issue is counted.
- Infographic wrapper contains zero or multiple child frames.
- Resource WebP does not exist and sibling PNG also does not exist.
- Figma token invalid/expired can produce 403 errors. Exact Figma auth status cannot be diagnosed from repo alone.

## Operational Notes

- Keep `PHOTO_EXPORT_RUN_MODE=standard` for normal runs.
- Use `retry_missed` to regenerate missed items without changing core overwrite behavior.
- Review missed CSV files after each run.
- Do not manually delete `image_refs_cache.json` unless you intend to force broader re-evaluation.
