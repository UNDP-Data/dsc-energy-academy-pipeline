from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.auxiliary.avatars.blob_status import (
    AvatarExpectation,
    avatar_expectation_exists,
    build_avatar_blob_status_rows,
    final_avatar_video_blob_name,
    heygen_avatar_video_blob_name,
    write_avatar_blob_status_csv,
)


class FakeAvatarBlobContainer:
    def __init__(self, names: set[str]) -> None:
        self.names = names

    def blob_exists(self, blob_name: str) -> bool:
        return blob_name in self.names

    def list_blob_names(self, prefix: str) -> list[str]:
        return sorted(name for name in self.names if name.startswith(prefix))


class AvatarBlobStatusTests(unittest.TestCase):
    def test_final_avatar_blob_path_matches_core_pipeline_path(self) -> None:
        self.assertEqual(
            final_avatar_video_blob_name("1.1.1", "en"),
            "Avatars/en/1/Videos/Lesson-1.1.1_en.mp4",
        )

    def test_expectation_accepts_final_blob(self) -> None:
        expectation = AvatarExpectation("1.1.1", "en")
        container = FakeAvatarBlobContainer({"Avatars/en/1/Videos/Lesson-1.1.1_en.mp4"})

        exists, matched = avatar_expectation_exists(expectation, container)

        self.assertTrue(exists)
        self.assertEqual(matched, "Avatars/en/1/Videos/Lesson-1.1.1_en.mp4")

    def test_expectation_accepts_heygen_part_blob(self) -> None:
        expectation = AvatarExpectation("1.1.1", "en", "2")
        blob_name = heygen_avatar_video_blob_name("1.1.1", "en", "2")
        container = FakeAvatarBlobContainer({blob_name})

        exists, matched = avatar_expectation_exists(expectation, container)

        self.assertTrue(exists)
        self.assertEqual(matched, blob_name)

    def test_expectation_accepts_heygen_prefix_when_part_is_unknown(self) -> None:
        expectation = AvatarExpectation("1.1.1", "en")
        blob_name = "AI_Avatars/Lesson-1.1.1_en_1.mp4"
        container = FakeAvatarBlobContainer({blob_name})

        exists, matched = avatar_expectation_exists(expectation, container)

        self.assertTrue(exists)
        self.assertEqual(matched, blob_name)

    def test_status_rows_aggregate_by_lesson(self) -> None:
        expectations = [
            AvatarExpectation("1.1.1", "en"),
            AvatarExpectation("1.1.1", "fr"),
            AvatarExpectation("1.1.2", "en"),
        ]
        container = FakeAvatarBlobContainer(
            {
                "Avatars/en/1/Videos/Lesson-1.1.1_en.mp4",
                "AI_Avatars/Lesson-1.1.2_en_1.mp4",
            }
        )

        rows = build_avatar_blob_status_rows(expectations, container)

        self.assertEqual(rows[0]["lesson_id"], "1.1.1")
        self.assertTrue(rows[0]["status"].startswith("partial: 1/2"))
        self.assertEqual(rows[1]["lesson_id"], "1.1.2")
        self.assertTrue(rows[1]["status"].startswith("complete: 1/1"))

    def test_write_avatar_blob_status_csv_has_required_columns(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "avatars.csv"
            output_path = root / "status.csv"
            input_path.write_text("Lesson,Language\n1.1.1,en\n", encoding="utf-8")
            container = FakeAvatarBlobContainer({"Avatars/en/1/Videos/Lesson-1.1.1_en.mp4"})

            result = write_avatar_blob_status_csv(
                input_path=input_path,
                output_path=output_path,
                container=container,
            )

            self.assertEqual(result["complete"], 1)
            with open(output_path, "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(rows[0].keys()), ["lesson_id", "status"])
            self.assertEqual(rows[0]["lesson_id"], "1.1.1")
            self.assertTrue(rows[0]["status"].startswith("complete:"))


if __name__ == "__main__":
    unittest.main()
