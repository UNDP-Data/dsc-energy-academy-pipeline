from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.photo.resumable import (  # noqa: E402
    PhotoExportJournal,
    RETRY_MISSED_RUN_MODE,
    STANDARD_RUN_MODE,
    fetch_image_bytes_with_retry,
    normalize_run_mode,
    select_scanned_nodes,
)


class PhotoResumableTests(unittest.TestCase):
    def test_normalize_run_mode_defaults_and_validates(self) -> None:
        self.assertEqual(normalize_run_mode(None), STANDARD_RUN_MODE)
        self.assertEqual(normalize_run_mode("retry_missed"), RETRY_MISSED_RUN_MODE)
        with self.assertRaises(ValueError):
            normalize_run_mode("full_refresh")

    def test_journal_rehydrates_successes_misses_and_completed_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = PhotoExportJournal.load(tmpdir, "image_upload")
            journal.record_success(
                blob_name="Modules/Module_1/a.webp",
                node_id="1:1",
                file_id="file-1",
                page_name="Module 1",
                url="https://example.com/a.png",
            )
            journal.record_miss(
                blob_name="Modules/Module_1/b.webp",
                node_id="1:2",
                file_id="file-1",
                page_name="Module 1",
                reason="no_bytes",
                detail="TimeoutError",
                url="https://example.com/b.png",
            )
            journal.record_page_completed(
                file_id="file-1",
                page_name="Module 1",
                summary={"uploaded": 1, "missed": 1},
            )

            reloaded = PhotoExportJournal.load(tmpdir, "image_upload")
            self.assertTrue(reloaded.is_successful("Modules/Module_1/a.webp"))
            self.assertTrue(reloaded.is_missed("Modules/Module_1/b.webp"))
            self.assertTrue(reloaded.page_is_completed("file-1", "Module 1"))
            self.assertTrue(reloaded.missed_csv_path.exists())
            self.assertTrue(reloaded.summary_path.exists())

    def test_standard_selection_skips_successes_misses_and_completed_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = PhotoExportJournal.load(tmpdir, "image_upload")
            journal.record_success(
                blob_name="Modules/Module_1/a.webp",
                node_id="1:1",
                file_id="file-1",
                page_name="Module 1",
                url="https://example.com/a.png",
            )
            journal.record_miss(
                blob_name="Modules/Module_1/b.webp",
                node_id="1:2",
                file_id="file-1",
                page_name="Module 1",
                reason="no_url",
                detail="missing",
            )
            scanned = {
                "1:1": {"blob_name": "Modules/Module_1/a.webp", "image_ref": "ref-a"},
                "1:2": {"blob_name": "Modules/Module_1/b.webp", "image_ref": "ref-b"},
                "1:3": {"blob_name": "Modules/Module_1/c.webp", "image_ref": "ref-c"},
            }

            selected, stats = select_scanned_nodes(
                scanned=scanned,
                existing_blobs=set(),
                previous_refs={},
                journal=journal,
                file_id="file-1",
                page_name="Module 1",
                overwrite=True,
                run_mode=STANDARD_RUN_MODE,
            )

            self.assertEqual(list(selected), ["1:3"])
            self.assertEqual(stats["already_successful"], 1)
            self.assertEqual(stats["already_missed"], 1)

            journal.record_page_completed(
                file_id="file-1",
                page_name="Module 1",
                summary={"uploaded": 1},
            )
            selected, stats = select_scanned_nodes(
                scanned=scanned,
                existing_blobs=set(),
                previous_refs={},
                journal=journal,
                file_id="file-1",
                page_name="Module 1",
                overwrite=True,
                run_mode=STANDARD_RUN_MODE,
            )
            self.assertEqual(selected, {})
            self.assertEqual(stats["already_completed_page"], 3)

    def test_retry_mode_selects_only_unresolved_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = PhotoExportJournal.load(tmpdir, "image_upload")
            journal.record_success(
                blob_name="Modules/Module_1/a.webp",
                node_id="1:1",
                file_id="file-1",
                page_name="Module 1",
                url="https://example.com/a.png",
            )
            journal.record_miss(
                blob_name="Modules/Module_1/b.webp",
                node_id="1:2",
                file_id="file-1",
                page_name="Module 1",
                reason="no_bytes",
                detail="TimeoutError",
            )
            scanned = {
                "1:1": {"blob_name": "Modules/Module_1/a.webp", "image_ref": "ref-a"},
                "1:2": {"blob_name": "Modules/Module_1/b.webp", "image_ref": "ref-b"},
                "1:3": {"blob_name": "Modules/Module_1/c.webp", "image_ref": "ref-c"},
            }

            selected, stats = select_scanned_nodes(
                scanned=scanned,
                existing_blobs=set(),
                previous_refs={},
                journal=journal,
                file_id="file-1",
                page_name="Module 1",
                overwrite=False,
                run_mode=RETRY_MISSED_RUN_MODE,
            )

            self.assertEqual(list(selected), ["1:2"])
            self.assertEqual(stats["already_successful"], 0)
            self.assertEqual(stats["already_missed"], 0)

    def test_standard_mode_bootstraps_from_existing_blob_and_cached_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            journal = PhotoExportJournal.load(tmpdir, "image_upload")
            scanned = {
                "1:1": {"blob_name": "Modules/Module_1/a.webp", "image_ref": "ref-a"},
                "1:2": {"blob_name": "Modules/Module_1/b.webp", "image_ref": "ref-b"},
            }

            selected, stats = select_scanned_nodes(
                scanned=scanned,
                existing_blobs={"Modules/Module_1/a.webp"},
                previous_refs={"1:1": "ref-a"},
                journal=journal,
                file_id="file-1",
                page_name="Module 1",
                overwrite=True,
                run_mode=STANDARD_RUN_MODE,
            )

            self.assertEqual(list(selected), ["1:2"])
            self.assertEqual(stats["up_to_date"], 1)

    def test_fetch_image_bytes_with_retry_uses_requests_fallback(self) -> None:
        class FakeSession:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, url):
                raise TimeoutError("aiohttp timeout")

        async def run_test():
            with patch("sea_pipeline.photo.resumable.aiohttp.ClientSession", FakeSession):
                with patch(
                    "sea_pipeline.photo.resumable.fetch_image_bytes_with_requests_fallback",
                    return_value=(b"fallback-bytes", ""),
                ) as fallback:
                    data, detail = await fetch_image_bytes_with_retry(
                        url="https://example.com/image.png",
                        log=lambda _: None,
                        attempts=2,
                        timeout_seconds=1,
                    )
            self.assertEqual(data, b"fallback-bytes")
            self.assertEqual(detail, "")
            self.assertEqual(fallback.call_count, 1)

        import asyncio

        asyncio.run(run_test())

    def test_fetch_image_bytes_with_retry_reports_failure_when_all_downloaders_fail(self) -> None:
        class FakeSession:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            def get(self, url):
                raise TimeoutError("aiohttp timeout")

        async def run_test():
            with patch("sea_pipeline.photo.resumable.aiohttp.ClientSession", FakeSession):
                with patch(
                    "sea_pipeline.photo.resumable.fetch_image_bytes_with_requests_fallback",
                    return_value=(None, "ReadTimeout"),
                ):
                    data, detail = await fetch_image_bytes_with_retry(
                        url="https://example.com/image.png",
                        log=lambda _: None,
                        attempts=1,
                        timeout_seconds=1,
                    )
            self.assertIsNone(data)
            self.assertEqual(detail, "ReadTimeout")

        import asyncio

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
