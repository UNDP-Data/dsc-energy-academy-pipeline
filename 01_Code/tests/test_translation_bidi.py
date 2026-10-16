from __future__ import annotations

import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.translation.bidi import add_bdi_tags_for_arabic, isolate_ltr_runs_for_arabic, normalize_arabic_cache_entries


class TranslationBidiTests(unittest.TestCase):
    def test_isolates_acronyms_in_arabic_text(self) -> None:
        self.assertEqual(
            add_bdi_tags_for_arabic("إطار DREI ونمذجة LCOE في COP28"),
            'إطار <bdi dir="ltr">DREI</bdi> ونمذجة <bdi dir="ltr">LCOE</bdi> في <bdi dir="ltr">COP28</bdi>',
        )

    def test_preserves_html_tags_and_isolates_text_nodes(self) -> None:
        self.assertEqual(
            add_bdi_tags_for_arabic('<a href="https://example.org/DREI"><u>DREI</u></a>'),
            '<a href="https://example.org/DREI"><u><bdi dir="ltr">DREI</bdi></u></a>',
        )

    def test_does_not_wrap_urls_or_double_wrap(self) -> None:
        text = 'راجع https://example.org/DREI وإطار <bdi dir="ltr">DREI</bdi>'

        self.assertEqual(add_bdi_tags_for_arabic(text), text)

    def test_converts_legacy_unicode_isolates_to_bdi_tags(self) -> None:
        self.assertEqual(
            add_bdi_tags_for_arabic("إطار \u2066DREI\u2069"),
            'إطار <bdi dir="ltr">DREI</bdi>',
        )

    def test_backward_compatible_alias_uses_bdi_tags(self) -> None:
        self.assertEqual(
            isolate_ltr_runs_for_arabic("إطار DREI"),
            'إطار <bdi dir="ltr">DREI</bdi>',
        )

    def test_normalizes_arabic_cache_entries(self) -> None:
        cache = {
            "one": {"ar": "إطار DREI", "fr": "DREI"},
            "two": {"ar": "بدون اختصار"},
        }

        self.assertEqual(normalize_arabic_cache_entries(cache), 1)
        self.assertEqual(cache["one"]["ar"], 'إطار <bdi dir="ltr">DREI</bdi>')
        self.assertEqual(cache["two"]["ar"], "بدون اختصار")


if __name__ == "__main__":
    unittest.main()
