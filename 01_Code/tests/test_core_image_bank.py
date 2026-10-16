from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.core.image_bank import apply_learning_card_image_bank, build_academy_image_bank


class CoreImageBankTests(unittest.TestCase):
    def test_build_image_bank_excludes_learning_and_takeaway_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir()
            self._write_lesson(
                lesson_dir / "1.1.1.json",
                [
                    self._segment("photo_full_height", "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/real.webp"),
                    self._learning_objectives("https://sehseadata.blob.core.windows.net/images/Modules/Module_1/placeholder.webp"),
                    self._segment("resource", "https://sehseadata.blob.core.windows.net/images/Resources/Module_1/resource-1.webp"),
                ],
            )

            bank = build_academy_image_bank(root)

            self.assertEqual([entry["src"] for entry in bank], ["https://sehseadata.blob.core.windows.net/images/Modules/Module_1/real.webp"])

    def test_assigns_learning_and_takeaway_images_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir()
            lesson_path = lesson_dir / "1.1.1.json"
            self._write_lesson(
                lesson_path,
                [
                    self._segment("photo_full_height", "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp"),
                    self._segment("lesson_cover", "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/b.webp"),
                    self._learning_objectives("https://sehseadata.blob.core.windows.net/images/Modules/Module_1/placeholder1.webp"),
                    self._key_takeaways("https://sehseadata.blob.core.windows.net/images/Modules/Module_1/placeholder2.webp"),
                ],
            )

            first = apply_learning_card_image_bank(root, seed=42)
            lesson_after_first = json.loads(lesson_path.read_text(encoding="utf-8"))
            second = apply_learning_card_image_bank(root, seed=42)
            lesson_after_second = json.loads(lesson_path.read_text(encoding="utf-8"))

            self.assertEqual(first["image_bank_count"], 2)
            self.assertEqual(first["updated_cards"], 2)
            self.assertEqual(second["updated_cards"], 0)
            self.assertEqual(lesson_after_first, lesson_after_second)
            assigned_sources = [
                lesson_after_first["segments"][2]["content"]["objectives"][0]["image"]["src"],
                lesson_after_first["segments"][3]["content"]["takeaways"][0]["image"]["src"],
            ]
            self.assertTrue(all(src.endswith(("/a.webp", "/b.webp")) for src in assigned_sources))
            self.assertTrue((root / "academy_image_bank.json").exists())

    def test_different_seed_can_change_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir()
            lesson_path = lesson_dir / "1.1.1.json"
            self._write_lesson(
                lesson_path,
                [
                    self._segment("photo_full_height", "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp"),
                    self._segment("photo_vertical", "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/b.webp"),
                    self._segment("lesson_cover", "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/c.webp"),
                    self._learning_objectives("https://sehseadata.blob.core.windows.net/images/Modules/Module_1/placeholder.webp"),
                ],
            )

            apply_learning_card_image_bank(root, seed=1)
            first_src = json.loads(lesson_path.read_text(encoding="utf-8"))["segments"][3]["content"]["objectives"][0]["image"]["src"]
            apply_learning_card_image_bank(root, seed=2)
            second_src = json.loads(lesson_path.read_text(encoding="utf-8"))["segments"][3]["content"]["objectives"][0]["image"]["src"]

            self.assertIn(first_src, {f"https://sehseadata.blob.core.windows.net/images/Modules/Module_1/{name}.webp" for name in "abc"})
            self.assertIn(second_src, {f"https://sehseadata.blob.core.windows.net/images/Modules/Module_1/{name}.webp" for name in "abc"})

    @staticmethod
    def _write_lesson(path: Path, segments: list[dict]) -> None:
        path.write_text(json.dumps({"id": path.stem, "segments": segments}), encoding="utf-8")

    @staticmethod
    def _segment(template_id: str, src: str) -> dict:
        return {"template_id": template_id, "content": {"image": {"src": src, "caption": "old"}}}

    @staticmethod
    def _learning_objectives(src: str) -> dict:
        return {
            "template_id": "learning_objectives",
            "content": {"objectives": [{"image": {"src": src, "caption": "placeholder"}, "title": "Objective", "description": ""}]},
        }

    @staticmethod
    def _key_takeaways(src: str) -> dict:
        return {
            "template_id": "key_takeaways",
            "content": {"takeaways": [{"image": {"src": src, "caption": "placeholder"}, "title": "Takeaway", "description": ""}]},
        }


if __name__ == "__main__":
    unittest.main()
