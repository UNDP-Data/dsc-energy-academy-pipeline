from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.auxiliary.photo_caption_matcher import (
    _extract_piwigo_image_url,
    evaluate_akaze_match,
    is_akaze_match_accepted,
    iter_lesson_image_candidates,
    normalize_piwigo_base_url,
    PiwigoHashRecord,
    caption_for_hash,
    evaluate_multihash_match,
    select_best_piwigo_match,
    should_process_caption,
    update_photo_captions_from_piwigo,
)


class FakeSegmentHash:
    def __init__(self, bits: int = 64) -> None:
        self.bits = bits

    def __len__(self) -> int:
        return self.bits


class FakeMultiHash:
    def __init__(self, name: str, segments: int, comparisons: dict[str, tuple[int, int, float]] | None = None) -> None:
        self.name = name
        self.segment_hashes = [FakeSegmentHash() for _ in range(segments)]
        self.comparisons = comparisons or {}

    def hash_diff(self, other: "FakeMultiHash", hamming_cutoff=None, bit_error_rate=None) -> tuple[int, int]:
        matches, total_distance, _ = self.comparisons.get(other.name, (0, 0, float(len(self.segment_hashes))))
        return matches, total_distance

    def __sub__(self, other: "FakeMultiHash", hamming_cutoff=None, bit_error_rate=None) -> float:
        matches, total_distance, score = self.comparisons.get(other.name, (0, 0, float(len(self.segment_hashes))))
        return score


class PhotoCaptionMatcherTests(unittest.TestCase):
    def _render_test_image_bytes(self, *, crop_box: tuple[int, int, int, int] | None = None, variant: str = "base") -> bytes:
        image = Image.new("RGB", (360, 260), "white")
        draw = ImageDraw.Draw(image)
        if variant == "base":
            draw.rectangle((20, 20, 160, 120), outline="navy", width=5)
            draw.ellipse((180, 30, 310, 150), outline="darkgreen", width=6)
            draw.line((15, 240, 340, 15), fill="crimson", width=4)
            draw.line((40, 150, 320, 210), fill="goldenrod", width=5)
            draw.text((48, 46), "SEA", fill="black")
            draw.text((200, 175), "AKAZE", fill="purple")
        else:
            draw.rectangle((35, 35, 320, 95), outline="black", width=5)
            draw.ellipse((70, 110, 180, 220), outline="teal", width=5)
            draw.polygon([(220, 110), (330, 150), (250, 235)], outline="maroon", width=5)
            draw.text((120, 185), "OTHER", fill="black")
        if crop_box is not None:
            image = image.crop(crop_box)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_normalize_piwigo_base_url_accepts_picture_page_url(self) -> None:
        self.assertEqual(
            normalize_piwigo_base_url("https://seh-sea-piwigo.azurewebsites.net/picture.php?/5007"),
            "https://seh-sea-piwigo.azurewebsites.net",
        )

    def test_normalize_piwigo_base_url_preserves_subpath_install(self) -> None:
        self.assertEqual(
            normalize_piwigo_base_url("https://example.com/gallery/picture.php?/5007"),
            "https://example.com/gallery",
        )

    def test_extract_piwigo_image_url_prefers_derivative_urls(self) -> None:
        url = _extract_piwigo_image_url(
            {
                "page_url": "https://gallery.example/picture.php?/5411",
                "derivatives": {
                    "thumb": {"url": "https://gallery.example/_data/i/thumb.jpg"},
                    "large": {"url": "https://gallery.example/_data/i/large.jpg"},
                },
            }
        )

        self.assertEqual(url, "https://gallery.example/_data/i/large.jpg")

    def test_evaluate_akaze_match_prefers_true_crop_over_distractor(self) -> None:
        source = self._render_test_image_bytes(variant="base")
        crop = self._render_test_image_bytes(crop_box=(35, 25, 300, 220), variant="base")
        distractor = self._render_test_image_bytes(variant="other")

        crop_metrics = evaluate_akaze_match(crop, source)
        distractor_metrics = evaluate_akaze_match(crop, distractor)

        self.assertIsNotNone(crop_metrics)
        self.assertIsNotNone(distractor_metrics)
        self.assertGreater(crop_metrics.inliers, distractor_metrics.inliers)
        self.assertGreater(crop_metrics.score, distractor_metrics.score)
        self.assertTrue(
            is_akaze_match_accepted(
                crop_metrics,
                min_good_matches=4,
                min_inliers=4,
                min_inlier_ratio=0.1,
                min_candidate_coverage=0.01,
            )
        )

    def test_should_process_caption_respects_skip_unknowns(self) -> None:
        self.assertTrue(should_process_caption("", skip_unknowns=True))
        self.assertFalse(should_process_caption("unknown", skip_unknowns=True))
        self.assertTrue(should_process_caption("unknown", skip_unknowns=False))
        self.assertFalse(should_process_caption("4914", skip_unknowns=False))

    def test_iter_lesson_image_candidates_skips_infographics_special_templates_and_non_photo_assets(self) -> None:
        lesson = {
            "segments": [
                {
                    "template_id": "photo-vertical",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/test.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "module_cover",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/HeaderImages/Modules/module1.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "chapter_cover",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/HeaderImages/Chapters/chapter11.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "infographic",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/info.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "connection_next",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/connection.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "learning_objectives",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/learning.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "key_takeaways",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/takeaway.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "lesson_cover",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/lesson-cover.webp",
                            "caption": "",
                        }
                    },
                },
                {
                    "template_id": "lesson_part_cover",
                    "content": {
                        "image": {
                            "src": "https://sehseadata.blob.core.windows.net/images/Lessons/frame/lesson111_frame.webp",
                            "caption": "",
                        }
                    },
                },
            ]
        }
        candidates = iter_lesson_image_candidates(lesson, skip_unknowns=True)
        self.assertEqual(len(candidates), 1)
        self.assertIn("segments[0]", candidates[0][0])

    def test_update_photo_captions_from_piwigo_updates_blank_and_unknown_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir(parents=True, exist_ok=True)
            lesson_path = lesson_dir / "1.1.1.json"
            lesson_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "photo-vertical",
                                "content": {
                                    "image": {
                                        "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp",
                                        "caption": "",
                                    }
                                },
                            },
                            {
                                "template_id": "photo-horizontal",
                                "content": {
                                    "image": {
                                        "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/b.webp",
                                        "caption": "unknown",
                                    }
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            piwigo_path = root / "piwigo.csv"
            piwigo_path.write_text("id,hash\n4914,hash-a\n4915,hash-b\n", encoding="utf-8")

            fake_bytes = {
                "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp": b"a",
                "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/b.webp": b"b",
            }
            fake_hashes = {b"a": "hash-a", b"b": "hash-b"}
            parsed_hashes = {
                "hash-a": FakeMultiHash("hash-a", 2, comparisons={"hash-a": (2, 0, 0.0), "hash-b": (0, 0, 2.0)}),
                "hash-b": FakeMultiHash("hash-b", 2, comparisons={"hash-a": (0, 0, 2.0), "hash-b": (2, 0, 0.0)}),
            }

            summary = update_photo_captions_from_piwigo(
                root,
                piwigo_path,
                skip_unknowns=False,
                test_run=False,
                fetcher=lambda src: fake_bytes[src],
                hash_computer=lambda image_bytes: fake_hashes[image_bytes],
                hash_parser=lambda hash_value: parsed_hashes[hash_value],
            )

            updated = json.loads(lesson_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["segments"][0]["content"]["image"]["caption"], "4914")
            self.assertEqual(updated["segments"][1]["content"]["image"]["caption"], "4915")
            self.assertEqual(summary["matched"], 2)

    def test_update_photo_captions_test_run_limits_lesson_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for idx in range(5):
                lesson_dir = root / f"Module_{idx + 1}"
                lesson_dir.mkdir(parents=True, exist_ok=True)
                (lesson_dir / f"{idx + 1}.1.0.json").write_text(
                    json.dumps(
                        {
                            "segments": [
                                {
                                    "template_id": "photo-vertical",
                                    "content": {
                                        "image": {
                                            "src": f"https://sehseadata.blob.core.windows.net/images/Modules/Module_1/{idx}.webp",
                                            "caption": "",
                                        }
                                    },
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

            piwigo_path = root / "piwigo.csv"
            piwigo_path.write_text("id,hash\n4914,hash-a\n", encoding="utf-8")

            summary = update_photo_captions_from_piwigo(
                root,
                piwigo_path,
                test_run=True,
                sample_size=3,
                fetcher=lambda src: b"a",
                hash_computer=lambda image_bytes: "hash-a",
                hash_parser=lambda hash_value: FakeMultiHash(hash_value, 2, comparisons={"hash-a": (2, 0, 0.0)}),
            )

            self.assertTrue(summary["test_run"])
            self.assertEqual(summary["scanned_lessons"], 3)

    def test_update_photo_captions_image_limit_stops_after_target_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for idx in range(5):
                lesson_dir = root / f"Module_{idx + 1}"
                lesson_dir.mkdir(parents=True, exist_ok=True)
                (lesson_dir / f"{idx + 1}.1.0.json").write_text(
                    json.dumps(
                        {
                            "segments": [
                                {
                                    "template_id": "photo-vertical",
                                    "content": {
                                        "image": {
                                            "src": f"https://sehseadata.blob.core.windows.net/images/Modules/Module_1/{idx}.webp",
                                            "caption": "",
                                        }
                                    },
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

            piwigo_path = root / "piwigo.csv"
            piwigo_path.write_text("id,hash\n4914,hash-a\n", encoding="utf-8")

            summary = update_photo_captions_from_piwigo(
                root,
                piwigo_path,
                image_limit=3,
                fetcher=lambda src: b"a",
                hash_computer=lambda image_bytes: "hash-a",
                hash_parser=lambda hash_value: FakeMultiHash(hash_value, 2, comparisons={"hash-a": (2, 0, 0.0)}),
            )

            self.assertEqual(summary["scanned_images"], 3)
            self.assertTrue(summary["stopped_after_image_limit"])

    def test_update_photo_captions_logs_lessons_and_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir(parents=True, exist_ok=True)
            lesson_path = lesson_dir / "1.1.1.json"
            lesson_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "photo-vertical",
                                "content": {
                                    "image": {
                                        "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp",
                                        "caption": "",
                                    }
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            piwigo_path = root / "piwigo.csv"
            piwigo_path.write_text("id,hash\n4914,hash-a\n", encoding="utf-8")
            lines: list[str] = []

            update_photo_captions_from_piwigo(
                root,
                piwigo_path,
                fetcher=lambda src: b"a",
                hash_computer=lambda image_bytes: "hash-a",
                hash_parser=lambda hash_value: FakeMultiHash(hash_value, 2, comparisons={"hash-a": (2, 0, 0.0)}),
                log=lines.append,
            )

            joined = "\n".join(lines)
            self.assertIn("Lesson Module_1/1.1.1.json: 1 eligible images", joined)
            self.assertIn("Image 1", joined)
            self.assertIn("result=matched", joined)
            self.assertIn("top_piwigo=4914", joined)

    def test_update_photo_captions_reports_best_piwigo_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir(parents=True, exist_ok=True)
            lesson_path = lesson_dir / "1.1.1.json"
            lesson_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "photo-vertical",
                                "content": {
                                    "image": {
                                        "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp",
                                        "caption": "",
                                    }
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            piwigo_path = root / "piwigo.csv"
            piwigo_path.write_text("id,hash\n4914,hash-a\n4915,hash-b\n", encoding="utf-8")
            events: list[dict[str, Any]] = []

            update_photo_captions_from_piwigo(
                root,
                piwigo_path,
                fetcher=lambda src: b"a",
                hash_computer=lambda image_bytes: "hash-a",
                hash_parser=lambda hash_value: FakeMultiHash(
                    hash_value,
                    2,
                    comparisons={
                        "hash-a": (2, 0, 0.0),
                        "hash-b": (1, 2, 0.9),
                    },
                ),
                piwigo_image_url_builder=lambda photo_id: f"https://piwigo.example/photos/{photo_id}.jpg",
                match_reporter=events.append,
            )

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["best_photo_id"], "4914")
            self.assertEqual(events[0]["best_piwigo_src"], "https://piwigo.example/photos/4914.jpg")
            self.assertEqual(events[0]["match_status"], "matched")

    def test_update_photo_captions_reports_best_candidate_even_when_caption_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lesson_dir = root / "Module_1"
            lesson_dir.mkdir(parents=True, exist_ok=True)
            lesson_path = lesson_dir / "1.1.1.json"
            lesson_path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "template_id": "photo-vertical",
                                "content": {
                                    "image": {
                                        "src": "https://sehseadata.blob.core.windows.net/images/Modules/Module_1/a.webp",
                                        "caption": "",
                                    }
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            piwigo_path = root / "piwigo.csv"
            piwigo_path.write_text("id,hash\n4914,hash-a\n4915,hash-b\n", encoding="utf-8")
            events: list[dict[str, Any]] = []

            parsed_hashes = {
                "candidate": FakeMultiHash(
                    "candidate",
                    2,
                    comparisons={
                        "hash-a": (0, 0, 0.40),
                        "hash-b": (0, 0, 0.85),
                    },
                ),
                "hash-a": FakeMultiHash("hash-a", 2),
                "hash-b": FakeMultiHash("hash-b", 2),
            }

            summary = update_photo_captions_from_piwigo(
                root,
                piwigo_path,
                fetcher=lambda src: b"a",
                hash_computer=lambda image_bytes: "candidate",
                hash_parser=lambda hash_value: parsed_hashes[hash_value],
                piwigo_image_url_builder=lambda photo_id: f"https://piwigo.example/photos/{photo_id}.jpg",
                match_reporter=events.append,
            )

            self.assertEqual(summary["unknown"], 1)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["match_status"], "unknown")
            self.assertEqual(events[0]["best_photo_id"], "4914")
            self.assertEqual(events[0]["best_piwigo_src"], "https://piwigo.example/photos/4914.jpg")

    def test_evaluate_multihash_match_allows_strong_single_region_match_but_rejects_weak_one(self) -> None:
        candidate = FakeMultiHash("candidate", 1, comparisons={"exact": (1, 0, 0.0), "fuzzy": (1, 10, 0.05)})
        exact = FakeMultiHash("exact", 1)
        fuzzy = FakeMultiHash("fuzzy", 1)

        exact_match = evaluate_multihash_match(candidate, exact)
        fuzzy_match = evaluate_multihash_match(candidate, fuzzy)

        self.assertIsNotNone(exact_match)
        self.assertIsNone(fuzzy_match)

    def test_evaluate_multihash_match_requires_candidate_coverage(self) -> None:
        candidate = FakeMultiHash("candidate", 3, comparisons={"partial": (1, 0, 0.10)})
        partial = FakeMultiHash("partial", 5)

        match = evaluate_multihash_match(candidate, partial)

        self.assertIsNone(match)

    def test_select_best_piwigo_match_rejects_ambiguous_near_ties(self) -> None:
        candidate = FakeMultiHash(
            "candidate",
            3,
            comparisons={
                "first": (2, 2, 0.60),
                "second": (2, 2, 0.68),
            },
        )
        records = [
            PiwigoHashRecord("4914", "hash-first", FakeMultiHash("first", 3)),
            PiwigoHashRecord("4915", "hash-second", FakeMultiHash("second", 3)),
        ]

        photo_id, status = select_best_piwigo_match(candidate, records)

        self.assertEqual(photo_id, "unknown")
        self.assertEqual(status, "ambiguous")

    def test_caption_for_hash_uses_best_unique_crop_match_not_string_equality(self) -> None:
        parsed_hashes = {
            "candidate": FakeMultiHash(
                "candidate",
                3,
                comparisons={
                    "stored-1": (2, 1, 0.45),
                    "stored-2": (0, 0, 3.0),
                },
            ),
            "stored-1": FakeMultiHash("stored-1", 4),
            "stored-2": FakeMultiHash("stored-2", 4),
        }
        records = [
            PiwigoHashRecord("4914", "stored-1", parsed_hashes["stored-1"]),
            PiwigoHashRecord("4915", "stored-2", parsed_hashes["stored-2"]),
        ]

        photo_id, status = caption_for_hash(
            "candidate",
            records,
            hash_parser=lambda hash_value: parsed_hashes[hash_value],
        )

        self.assertEqual(photo_id, "4914")
        self.assertEqual(status, "matched")


if __name__ == "__main__":
    unittest.main()
