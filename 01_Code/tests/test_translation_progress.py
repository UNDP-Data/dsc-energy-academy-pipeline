from __future__ import annotations

import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.translation.progress import (
    cache_entry_complete,
    cache_language_complete,
    count_uncached_sentence_chars,
    grouped_fallback_batches_after_full_attempt,
    language_batches_for_missing,
    merge_translation_batch,
    missing_cache_languages,
    sentence_needs_translation,
)


class TranslationProgressTests(unittest.TestCase):
    def test_cache_entry_complete_requires_all_target_languages(self) -> None:
        self.assertTrue(cache_entry_complete({"fr": "Bonjour", "es": "Hola"}, ["fr", "es"]))
        self.assertFalse(cache_entry_complete({"fr": "Bonjour"}, ["fr", "es"]))
        self.assertFalse(cache_entry_complete({"fr": "Bonjour", "es": "[needs translation] Hello"}, ["fr", "es"]))

    def test_sentence_needs_translation_uses_cache_state(self) -> None:
        cache = {
            "ok": {"fr": "Bonjour", "es": "Hola"},
            "partial": {"fr": "Bonjour", "es": ""},
        }

        self.assertFalse(sentence_needs_translation("ok", cache, ["fr", "es"]))
        self.assertTrue(sentence_needs_translation("partial", cache, ["fr", "es"]))
        self.assertTrue(sentence_needs_translation("missing", cache, ["fr", "es"]))

    def test_missing_cache_languages_reports_partial_entries(self) -> None:
        cache_entry = {"fr": "Bonjour", "es": "[needs translation] Hello", "pt": ""}

        self.assertTrue(cache_language_complete(cache_entry, "fr"))
        self.assertFalse(cache_language_complete(cache_entry, "es"))
        self.assertEqual(missing_cache_languages(cache_entry, ["fr", "es", "pt", "ar"]), ["es", "pt", "ar"])

    def test_language_batches_for_missing_uses_configured_groups(self) -> None:
        batches = language_batches_for_missing(
            ["es", "zh", "de", "fr"],
            [["fr", "es", "pt"], ["ar", "zh", "ru"]],
        )

        self.assertEqual(batches, [["fr", "es"], ["zh"], ["de"]])

    def test_grouped_fallback_batches_skip_duplicate_full_retry(self) -> None:
        self.assertEqual(
            grouped_fallback_batches_after_full_attempt(
                ["fr", "es", "pt", "ar"],
                [["fr", "es", "pt"], ["ar", "zh", "ru"]],
            ),
            [["fr", "es", "pt"], ["ar"]],
        )
        self.assertEqual(
            grouped_fallback_batches_after_full_attempt(
                ["fr", "es", "pt"],
                [["fr", "es", "pt"], ["ar", "zh", "ru"]],
            ),
            [],
        )

    def test_merge_translation_batch_preserves_existing_cache_languages(self) -> None:
        merged = merge_translation_batch(
            {"fr": "Bonjour"},
            "Hello",
            ["es", "pt"],
            {"es": "Hola"},
        )

        self.assertEqual(merged["en"], "Hello")
        self.assertEqual(merged["fr"], "Bonjour")
        self.assertEqual(merged["es"], "Hola")
        self.assertEqual(merged["pt"], "[needs translation] Hello")

    def test_merge_translation_batch_isolates_arabic_acronyms(self) -> None:
        merged = merge_translation_batch(
            {},
            "DREI and LCOE",
            ["ar"],
            {"ar": "إطار DREI ونمذجة LCOE"},
        )

        self.assertEqual(
            merged["ar"],
            'إطار <bdi dir="ltr">DREI</bdi> ونمذجة <bdi dir="ltr">LCOE</bdi>',
        )

    def test_count_uncached_sentence_chars_counts_only_api_work(self) -> None:
        rows = [
            {"sentence_hash": "cached", "sentence_text": "cached text"},
            {"sentence_hash": "new", "sentence_text": "new text"},
            {"sentence_hash": "needs", "sentence_text": "retry"},
        ]
        cache = {
            "cached": {"fr": "FR cached", "es": "ES cached"},
            "needs": {"fr": "FR retry", "es": "[needs translation] retry"},
        }

        self.assertEqual(
            count_uncached_sentence_chars(rows, cache, ["fr", "es"]),
            len("new text") + len("retry"),
        )


if __name__ == "__main__":
    unittest.main()
