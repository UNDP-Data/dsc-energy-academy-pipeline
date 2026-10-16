from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.translation.manual_cache import import_manual_translation_cache


class ManualTranslationCacheTests(unittest.TestCase):
    def test_imports_manual_arabic_with_bdi_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_dir = root / "manual"
            cache_file = root / "translations_cache.json"
            manual_dir.mkdir()
            cache_file.write_text(json.dumps({"hash1": {"en": "DREI framework"}}), encoding="utf-8")
            (manual_dir / "ar-manual.json").write_text(
                json.dumps({"hash1": {"en": "DREI framework", "text": "إطار DREI"}}),
                encoding="utf-8",
            )

            result = import_manual_translation_cache(
                manual_dir=manual_dir,
                translations_cache_file=cache_file,
                target_languages=["ar"],
            )

            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            self.assertEqual(result["imported"], 1)
            self.assertEqual(cache["hash1"]["ar"], 'إطار <bdi dir="ltr">DREI</bdi>')

    def test_skips_unedited_placeholders_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_dir = root / "manual"
            cache_file = root / "translations_cache.json"
            manual_dir.mkdir()
            cache_file.write_text(json.dumps({}), encoding="utf-8")
            (manual_dir / "ar-manual.json").write_text(
                json.dumps({"hash1": {"en": "Hello", "text": "[needs translation] Hello"}}),
                encoding="utf-8",
            )

            result = import_manual_translation_cache(
                manual_dir=manual_dir,
                translations_cache_file=cache_file,
                target_languages=["ar"],
            )

            self.assertEqual(result["imported"], 0)
            self.assertEqual(json.loads(cache_file.read_text(encoding="utf-8")), {})

    def test_normalizes_existing_arabic_cache_on_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manual_dir = root / "manual"
            cache_file = root / "translations_cache.json"
            manual_dir.mkdir()
            cache_file.write_text(json.dumps({"hash1": {"ar": "نمذجة LCOE"}}), encoding="utf-8")

            result = import_manual_translation_cache(
                manual_dir=manual_dir,
                translations_cache_file=cache_file,
                target_languages=["ar"],
            )

            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            self.assertEqual(result["normalized_existing_arabic"], 1)
            self.assertEqual(cache["hash1"]["ar"], 'نمذجة <bdi dir="ltr">LCOE</bdi>')


if __name__ == "__main__":
    unittest.main()
