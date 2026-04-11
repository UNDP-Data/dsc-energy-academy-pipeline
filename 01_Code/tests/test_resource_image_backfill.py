from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.auxiliary.resource_image_backfill import (
    backfill_resource_webp_images,
    convert_png_bytes_to_webp,
    iter_resource_image_urls,
    sibling_png_blob_name,
)


class FakeBlobContainer:
    def __init__(self, blobs: dict[str, bytes] | None = None, container_name: str = "images") -> None:
        self.container_name = container_name
        self.blobs = dict(blobs or {})
        self.uploads: list[tuple[str, bytes, str, bool]] = []

    def blob_exists(self, blob_name: str) -> bool:
        return blob_name in self.blobs

    def download_blob_bytes(self, blob_name: str) -> bytes:
        return self.blobs[blob_name]

    def upload_blob_bytes(
        self,
        blob_name: str,
        data: bytes,
        *,
        content_type: str,
        overwrite: bool,
    ) -> None:
        self.blobs[blob_name] = data
        self.uploads.append((blob_name, data, content_type, overwrite))


def make_png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    output = BytesIO()
    Image.new("RGBA", size=size, color=(255, 0, 0, 255)).save(output, format="PNG")
    return output.getvalue()


class ResourceImageBackfillTests(unittest.TestCase):
    def test_iter_resource_image_urls_collects_unique_resource_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            module_dir = root / "Module_1"
            module_dir.mkdir(parents=True, exist_ok=True)
            lesson_path = module_dir / "1.1.1.json"
            lesson_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "key_resources",
                                "content": {
                                    "resources": [
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_1/resource-1111.webp",
                                                "caption": "",
                                            }
                                        },
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_1/resource-1111.webp",
                                                "caption": "",
                                            }
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            urls = iter_resource_image_urls(root)

            self.assertEqual(
                urls,
                ["https://sehseadata.blob.core.windows.net/images/Resources/Module_1/resource-1111.webp"],
            )

    def test_convert_png_bytes_to_webp_returns_webp_bytes(self) -> None:
        webp_bytes = convert_png_bytes_to_webp(make_png_bytes())
        with Image.open(BytesIO(webp_bytes)) as image:
            self.assertEqual(image.format, "WEBP")

    def test_backfill_resource_webp_images_converts_missing_webp_from_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            module_dir = root / "Module_2"
            module_dir.mkdir(parents=True, exist_ok=True)
            lesson_path = module_dir / "2.1.1.json"
            lesson_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "key_resources",
                                "content": {
                                    "resources": [
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_2/resource-2111.webp",
                                                "caption": "",
                                            }
                                        },
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_2/resource-2112.webp",
                                                "caption": "",
                                            }
                                        },
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_2/resource-2113.webp",
                                                "caption": "",
                                            }
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            existing_webp = "Resources/Module_2/resource-2111.webp"
            png_only = sibling_png_blob_name("Resources/Module_2/resource-2112.webp")
            fake_container = FakeBlobContainer(
                {
                    existing_webp: b"already-webp",
                    png_only: make_png_bytes(),
                }
            )

            result = backfill_resource_webp_images(
                root,
                container=fake_container,
                overwrite=True,
            )

            self.assertEqual(result["scanned_resources"], 3)
            self.assertEqual(result["existing_webp"], 1)
            self.assertEqual(result["converted_from_png"], 1)
            self.assertEqual(result["missing_both"], 1)
            self.assertEqual(result["errors"], 0)
            self.assertEqual(len(fake_container.uploads), 1)
            uploaded_blob_name, _, content_type, overwrite = fake_container.uploads[0]
            self.assertEqual(uploaded_blob_name, "Resources/Module_2/resource-2112.webp")
            self.assertEqual(content_type, "image/webp")
            self.assertTrue(overwrite)

    def test_backfill_resource_webp_images_logs_each_resource_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            module_dir = root / "Module_3"
            module_dir.mkdir(parents=True, exist_ok=True)
            (module_dir / "3.1.1.json").write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "key_resources",
                                "content": {
                                    "resources": [
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_3/resource-3111.webp",
                                                "caption": "",
                                            }
                                        },
                                        {
                                            "image": {
                                                "src": "https://sehseadata.blob.core.windows.net/images/Resources/Module_3/resource-3112.webp",
                                                "caption": "",
                                            }
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            fake_container = FakeBlobContainer(
                {
                    "Resources/Module_3/resource-3111.webp": b"already-webp",
                    "Resources/Module_3/resource-3112.png": make_png_bytes(),
                }
            )
            lines: list[str] = []

            backfill_resource_webp_images(
                root,
                container=fake_container,
                log=lines.append,
            )

            self.assertEqual(len(lines), 2)
            self.assertIn("Existing WebP", lines[0])
            self.assertIn("Converted PNG to WebP", lines[1])


if __name__ == "__main__":
    unittest.main()
