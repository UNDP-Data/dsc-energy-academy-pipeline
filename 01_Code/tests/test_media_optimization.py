from __future__ import annotations

import copy
import json
import struct
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sea_pipeline.photo.media_optimization import (
    MANIFEST_NAME, ORIGINAL_PREFIX, MediaOptions, blob_name_from_url,
    image_roles, mp4_has_faststart, optimize_container_media, prepare_image,
)
from sea_pipeline.photo.media_restore import restore_original


def png(size=(800, 400)):
    stream = BytesIO()
    Image.new("RGBA", size, (100, 150, 200, 120)).save(stream, "PNG")
    return stream.getvalue()


class FakeContainer:
    url = "https://example.blob.core.windows.net/images?sig=SECRET"

    def __init__(self):
        self.blobs = {}
        self.fail_variant = False
        self.concurrent_edit = False

    def list_blobs(self):
        return [copy.deepcopy(value[1]) for value in self.blobs.values()]

    def get_blob_client(self, name):
        store = self

        class Blob:
            url = "https://example.blob.core.windows.net/images/" + name

            def get_blob_properties(self):
                if name not in store.blobs:
                    raise ResourceNotFoundError("missing")
                return copy.deepcopy(store.blobs[name][1])

            def download_blob(self, **kwargs):
                props = self.get_blob_properties()
                data = store.blobs[name][0]
                start = kwargs.get("offset", 0)
                data = data[start:start + kwargs.get("length", len(data))]
                return SimpleNamespace(readall=lambda: data, readinto=lambda s: s.write(data), properties=props)

            def upload_blob(self, data, overwrite=False, **kwargs):
                if name in store.blobs and not overwrite:
                    raise ResourceExistsError("exists")
                if kwargs.get("etag") and (store.concurrent_edit or kwargs["etag"] != self.get_blob_properties().etag):
                    raise ResourceModifiedError("concurrent edit")
                if store.fail_variant and name.startswith("media-optimized/") and name.endswith(".webp"):
                    raise RuntimeError("simulated upload failure")
                if hasattr(data, "read"):
                    data = data.read()
                prior = store.blobs.get(name)
                version = int(prior[1].etag) + 1 if prior else 1
                props = SimpleNamespace(name=name, size=len(data), etag=str(version), metadata=kwargs.get("metadata", {}),
                                        content_settings=kwargs.get("content_settings", ContentSettings(content_type="image/png")))
                store.blobs[name] = (data, props)
                return {"etag": props.etag}

            def set_http_headers(self, settings, **kwargs):
                return self.upload_blob(store.blobs[name][0], overwrite=True, content_settings=settings,
                                        metadata=self.get_blob_properties().metadata, **kwargs)

            def set_blob_metadata(self, metadata, **kwargs):
                return self.upload_blob(store.blobs[name][0], overwrite=True, metadata=metadata,
                                        content_settings=self.get_blob_properties().content_settings, **kwargs)

            def upload_blob_from_url(self, source_url, **kwargs):
                from urllib.parse import unquote
                source_name = unquote(source_url.split('/images/', 1)[1])
                return self.upload_blob(store.blobs[source_name][0], **kwargs)

        return Blob()


class MediaOptimizationTests(unittest.TestCase):
    def test_no_upscaling_and_alpha_preserved(self):
        result = prepare_image(png((100, 50)), "tiny.png", "photo", MediaOptions())
        self.assertEqual([v["width"] for v in result["variants"]], [100])
        image = Image.open(BytesIO(result["variants"][0]["data"]))
        self.assertEqual(image.size, (100, 50))
        self.assertIn("A", image.getbands())

    def test_graphic_full_resolution_and_pixels_preserved(self):
        raw = png((2000, 100))
        result = prepare_image(raw, "diagram.png", "graphic", MediaOptions(photo_max_edge=300))
        image = Image.open(BytesIO(result["original"]))
        self.assertEqual(image.size, (2000, 100))
        self.assertEqual(image.getpixel((10, 10)), (100, 150, 200, 120))

    def test_photo_resize_never_increases_bytes(self):
        raw = png((2000, 1000))
        result = prepare_image(raw, "photo.png", "photo", MediaOptions(photo_max_edge=600))
        self.assertLessEqual(len(result["original"]), len(raw))
        self.assertLessEqual(max(Image.open(BytesIO(result["original"])).size), 600)

    def test_graphic_jpeg_is_not_lossily_reencoded(self):
        stream = BytesIO()
        Image.effect_noise((800, 400), 40).convert("RGB").save(stream, "JPEG", quality=100)
        raw = stream.getvalue()
        result = prepare_image(raw, "diagram.jpg", "graphic", MediaOptions())
        self.assertEqual(result["original"], raw)

    def test_graphic_usage_overrides_photo_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            url = "https://example.blob.core.windows.net/images/a.webp"
            (root / "1.json").write_text(json.dumps({"segments": [
                {"template_id": "photo_horizontal", "content": {"image": {"src": url}}},
                {"template_id": "infographic", "content": {"image": {"src": url}}},
            ]}))
            self.assertEqual(image_roles(root, FakeContainer.url)["a.webp"], "graphic")
            self.assertIsNone(blob_name_from_url("https://other.example/images/a.webp", FakeContainer.url))

    def test_faststart_boxes(self):
        box = lambda kind: struct.pack(">I4s", 8, kind)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "video.mp4"
            path.write_bytes(box(b"ftyp") + box(b"moov") + box(b"mdat"))
            self.assertTrue(mp4_has_faststart(path))
            path.write_bytes(box(b"ftyp") + box(b"mdat") + box(b"moov"))
            self.assertFalse(mp4_has_faststart(path))

    def test_backups_manifest_resume_and_changed_source(self):
        store = FakeContainer()
        raw = png()
        name = "HeaderImages/test.png"
        store.get_blob_client(name).upload_blob(raw)
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = dict(lesson_root=Path(tmp), report_dir=Path(tmp) / "reports", options=MediaOptions(scope="all", workers=2), log=lambda _: None)
            result = optimize_container_media(store, **kwargs)
            self.assertEqual(result["summary"]["optimized"], 1)
            backups = [n for n in store.blobs if n.startswith(ORIGINAL_PREFIX)]
            self.assertEqual(store.blobs[backups[0]][0], raw)
            self.assertNotIn("SECRET", json.dumps(json.loads(store.blobs[MANIFEST_NAME][0])))
            result = optimize_container_media(store, **kwargs)
            self.assertEqual(result["summary"]["resumed"], 1)
            # A killed process may have only a local checkpoint, not a published manifest.
            del store.blobs[MANIFEST_NAME]
            self.assertEqual(optimize_container_media(store, **kwargs)["summary"]["resumed"], 1)
            # Fresh export resets metadata; a changed ETag must invalidate resume.
            store.get_blob_client(name).upload_blob(png((810, 410)), overwrite=True)
            result = optimize_container_media(store, **kwargs)
            self.assertEqual(result["summary"]["optimized"], 1)

    def test_failed_variant_does_not_replace_original_and_can_retry(self):
        store = FakeContainer()
        raw = png()
        store.get_blob_client("photo.png").upload_blob(raw)
        store.fail_variant = True
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = dict(lesson_root=Path(tmp), report_dir=Path(tmp) / "report", options=MediaOptions(scope="all"), log=lambda _: None)
            result = optimize_container_media(store, **kwargs)
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertEqual(store.blobs["photo.png"][0], raw)
            self.assertEqual(json.loads(store.blobs[MANIFEST_NAME][0])["images"], {})
            store.fail_variant = False
            self.assertEqual(optimize_container_media(store, **kwargs)["summary"]["optimized"], 1)

    def test_changed_recipe_uses_backup_not_lossy_output(self):
        store = FakeContainer()
        raw = png((1200, 600))
        name = "HeaderImages/test.png"
        store.get_blob_client(name).upload_blob(raw)
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = dict(lesson_root=Path(tmp), report_dir=Path(tmp) / "report", log=lambda _: None)
            optimize_container_media(store, options=MediaOptions(scope="all", photo_max_edge=300), **kwargs)
            optimize_container_media(store, options=MediaOptions(scope="all", photo_max_edge=600), **kwargs)
            self.assertEqual(Image.open(BytesIO(store.blobs[name][0])).width, 600)
            self.assertEqual(len([n for n in store.blobs if n.startswith(ORIGINAL_PREFIX)]), 1)

    def test_remote_video_ready_to_stream_avoids_backup(self):
        store = FakeContainer()
        raw = b"".join(struct.pack(">I4s", 8, tag) for tag in (b"ftyp", b"moov", b"mdat"))
        store.get_blob_client("video.mp4").upload_blob(raw)
        with tempfile.TemporaryDirectory() as tmp:
            result = optimize_container_media(store, lesson_root=Path(tmp), report_dir=Path(tmp) / "report", options=MediaOptions(scope="all"), log=lambda _: None)
            self.assertEqual(result["summary"]["optimized"], 1)
            self.assertEqual(store.blobs["video.mp4"][0], raw)
            self.assertFalse(any(n.startswith(ORIGINAL_PREFIX) for n in store.blobs))

    def test_restore_removes_mapping_and_restores_bytes(self):
        store = FakeContainer()
        name = "HeaderImages/test.png"
        raw = png((1200, 600))
        store.get_blob_client(name).upload_blob(raw)
        with tempfile.TemporaryDirectory() as tmp:
            optimize_container_media(store, lesson_root=Path(tmp), report_dir=Path(tmp) / "report",
                                     options=MediaOptions(scope="all", photo_max_edge=300), log=lambda _: None)
            result = restore_original(store, name)
            self.assertEqual(result["status"], "restored")
            self.assertEqual(store.blobs[name][0], raw)
            self.assertNotIn(name, json.loads(store.blobs[MANIFEST_NAME][0])["images"])

    def test_etag_conflict_does_not_overwrite_source(self):
        store = FakeContainer()
        name = "HeaderImages/test.png"
        raw = png((1200, 600))
        store.get_blob_client(name).upload_blob(raw)
        store.concurrent_edit = True
        with tempfile.TemporaryDirectory() as tmp:
            result = optimize_container_media(store, lesson_root=Path(tmp), report_dir=Path(tmp) / "report",
                                              options=MediaOptions(scope="all", photo_max_edge=300), log=lambda _: None)
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertEqual(store.blobs[name][0], raw)


    def test_default_scope_only_processes_structure_images(self):
        store = FakeContainer()
        names = ["HeaderImages/Modules/module1.png", "Lessons/frame/lesson111_frame.png",
                 "Modules/Module_1/content.png", "Avatars/en/1/Photos/poster.png"]
        for name in names:
            store.get_blob_client(name).upload_blob(png())
        original_content = copy.deepcopy(store.blobs[names[2]])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            urls = ["https://example.blob.core.windows.net/images/" + n for n in names[:2]]
            (root / "module_structure.json").write_text(json.dumps({"modules": [
                {"image": {"src": urls[0]}, "frame": {"src": urls[1]}},
                {"image": {"src": "https://example.blob.core.windows.net/images/missing.png"}},
            ]}))
            result = optimize_container_media(store, lesson_root=root, report_dir=root / "report", log=lambda _: None)
            self.assertEqual(result["scope"], "ui")
            self.assertEqual(result["summary"]["optimized"], 2)
            self.assertEqual(result["missing_ui_images"], ["missing.png"])
            self.assertEqual(store.blobs[names[2]], original_content)
            self.assertEqual(store.blobs[names[3]][1].etag, "1")
            self.assertEqual(set(json.loads(store.blobs[MANIFEST_NAME][0])["images"]), set(names[:2]))

    def test_ui_scope_requires_structure_not_whole_container_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                optimize_container_media(FakeContainer(), lesson_root=Path(tmp), report_dir=Path(tmp) / "report")


if __name__ == "__main__":
    unittest.main()
