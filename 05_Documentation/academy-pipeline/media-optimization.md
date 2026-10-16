# Academy media optimization

Run `media_optimization` in `01_Code/photo-export.ipynb` after photo and infographic
exports. It also works independently on existing Azure uploads and does not call
Figma, regenerate lessons, or translate content. **The default scope is UI-only**:
module/chapter covers and lesson thumbnails referenced by `module_structure.json`.
Lesson-body photos, resources, infographics, avatar posters and videos are excluded.
Missing structure references are reported, never replaced with a whole-container scan.

## Running

From the repository root:

```sh
pip3 install Pillow azure-storage-blob python-dotenv
PYTHONPATH=01_Code python3 -u -m sea_pipeline.photo.media_optimization --limit 10
PYTHONPATH=01_Code python3 -u -m sea_pipeline.photo.media_optimization --scope ui --no-video
```

`SAS_URL` in `01_Code/.env` must identify the images container and permit read,
list, create, and write. Expired SAS credentials are rejected before work starts.
Restart the notebook kernel after updating its environment. CLI runs reload the
file automatically. Alternatively, unset `SAS_URL`, set
`AZURE_STORAGE_CONTAINER_URL`, install `azure-identity`, and use an Azure CLI login
with Blob access. `ffmpeg` is required when a video needs fast-start remuxing.

The notebook exposes scope, widths, quality, maximum photo edge, original optimization,
video fast-start, an optional blob prefix, and an optional sample limit. Defaults
are 320/640/960/1440/1920 pixels, WebP quality 82, and twelve concurrent workers.
The sample limit counts assets, not lessons. It performs real writes.

## Asset policy

The policies below describe the supported encoders. Only structure-referenced UI
images are selected by default. Processing content or videos requires a separate,
explicit `--scope all` run; that is not part of the current UI optimization rollout.

- JPEG, PNG and WebP photos get aspect-preserving responsive WebP variants.
  Photographic originals are capped at a 1920-pixel longest edge. Existing URLs
  keep their file format and are replaced only when the encoded result saves 5%.
- Infographics, resource covers, image hotspots, charts and unknown graphics
  retain their full original dimensions and use lossless compression. Smaller
  variants are lossless encodings of resized images. Photos shared with a known
  graphic template receive the conservative graphic policy.
- Variants never upscale and are only retained when smaller than the original
  that will be served. The source remains the fallback when there is no useful
  variant, including high-resolution infographic requests.
- MP4s are checked using range reads. Files with metadata already at the front
  get cache headers without downloading the video. Other MP4s are remuxed using
  `ffmpeg -map 0 -c copy -movflags +faststart`; audio/video streams are not
  re-encoded. This improves playback startup, not the video bitrate.
- SVG and animated assets are preserved. PDFs and unrecognized file types are
  outside this image/video optimization stage. No files are deleted.

## Backups, retries and concurrency

Before changing raster or remuxed video bytes, the original is copied **within
Azure** to `media-originals/<sha256>/<original-path>`. Encoding-policy changes use
that backup, preventing progressive quality loss from repeated encoding. Source
ETags guard reads, backups and replacements against concurrent editing.

Variants use `media-optimized/<content-and-policy-hash>/<width>.webp`. These paths
are immutable and cache for one year. Original paths cache for one day. The
frontend manifest caches for five minutes. Blob metadata identifies the backup.
Backups and variants add storage; the primary saving is browser transfer and
rendering work, not necessarily total container size.

`03_Outputs/Media_Optimization/` contains a per-asset CSV, a local manifest
checkpoint, and a final summary JSON. Logs show each asset's status and bytes
before/after. Failed uploads never enter the published manifest. Rerunning checks
source ETags, recipe hashes, and variant existence, skips unchanged successes,
and retries failures. A local checkpoint can recover assets completed between
Azure manifest publications. Missing credentials or a manifest write conflict
stop the run; run only one optimizer at a time. Large transfers use 4 MiB chunks.

To restore a single asset, stop active optimization first:

```sh
PYTHONPATH=01_Code python3 -m sea_pipeline.photo.media_restore HeaderImages/Modules/module1.webp
```

Restoration reinstates the original bytes, metadata and headers and removes that
asset from the published variant mapping. Browser/server caches may continue to
serve the old image until their TTL expires. Original backups are kept.

## Frontend and backend integration

The frontend's `AcademyImage` wrapper preserves Next.js responsive `srcset`
behavior and routes UI raster images in `HeaderImages/` and `Lessons/image/` or
`Lessons/frame/` to `/api/media/image`. Content templates retain their original
Next.js image handling. That endpoint
selects an uploaded width from `media-optimized/manifest.json` and redirects to
the immutable Blob URL. A shared in-memory server cache prevents repeated
manifest downloads, including inventories larger than Next's fetch-cache limit.
Missing manifests/assets fall back to the normal Next.js optimizer; the image
component also retries the original when a variant fails to load.

Module/chapter cards and lesson cards have display-specific `sizes`. Content
photos, background photos, video posters and videos are unchanged by the frontend
integration. Local/static/external images keep the Next.js optimizer.

Deploy the frontend changes to activate this selection logic. The existing
standalone Next.js deployment supports the new API route; the legacy static
export configuration does not support it. Existing JSON fields and Strapi sync
contracts are unchanged. If Strapi imports images to different paths, those
assets must also be processed in the relevant container, or they use fallback.

Azure originals at existing URLs improve without a JSON/Strapi resync, subject
to existing browser/Next.js caches. Run this stage after future media exports so
the manifest follows changed sources. There is no automatic frontend deployment
or cache purge in this pipeline.
