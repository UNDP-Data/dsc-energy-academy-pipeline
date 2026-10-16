from __future__ import annotations

import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from entities.components import Card, clean_takeaway_description_prefix, split_first_sentence
from entities.frames import ModuleText
from sea_pipeline.core.lesson_text import (
    apply_ai_keyword_tags,
    find_triple_line_break_issues,
    normalize_text_for_line_break_validation,
)


class DummyNode:
    def __init__(
        self,
        *,
        name: str,
        node_type: str,
        node_id: str = "node-id",
        characters: str = "",
        children: list["DummyNode"] | None = None,
    ) -> None:
        self.name = name
        self.type = node_type
        self.id = node_id
        self.characters = characters
        self.children = children or []
        self.style = {}
        self.characterStyleOverrides = []
        self.styleOverrideTable = {}

    def select_node(self, node_type: str, name: str | None = None):
        for child in self.children:
            if child.type != node_type:
                continue
            if name is None or child.name == name:
                return child
        return None

    def select_nodes(self, node_type: str, name: str | None = None):
        results = []
        for child in self.children:
            if child.type != node_type:
                continue
            if name is None or child.name == name:
                results.append(child)
        return results


class LessonTextProcessingTests(unittest.TestCase):
    def test_split_first_sentence_returns_title_and_description(self) -> None:
        title, description = split_first_sentence("First sentence. Second sentence here.")
        self.assertEqual(title, "First sentence.")
        self.assertEqual(description, "Second sentence here.")

    def test_card_can_split_title_into_description_for_takeaways(self) -> None:
        image_group = DummyNode(
            name="image",
            node_type="GROUP",
            children=[DummyNode(name="image-rect", node_type="RECTANGLE")],
        )
        node = DummyNode(
            name="objective",
            node_type="GROUP",
            children=[
                image_group,
                DummyNode(name="title", node_type="TEXT", characters="Main takeaway. Supporting detail follows."),
            ],
        )

        card = Card.from_node(node, split_title_from_description=True)

        self.assertEqual(card.title, "Main takeaway.")
        self.assertEqual(card.description, "Supporting detail follows.")

    def test_card_removes_stray_dash_after_first_takeaway_sentence(self) -> None:
        image_group = DummyNode(
            name="image",
            node_type="GROUP",
            children=[DummyNode(name="image-rect", node_type="RECTANGLE")],
        )
        node = DummyNode(
            name="objective",
            node_type="GROUP",
            children=[
                image_group,
                DummyNode(name="title", node_type="TEXT", characters="Main takeaway. - Supporting detail follows."),
            ],
        )

        card = Card.from_node(node, split_title_from_description=True)

        self.assertEqual(card.title, "Main takeaway.")
        self.assertEqual(card.description, "Supporting detail follows.")

    def test_takeaway_dash_cleanup_preserves_hyphenated_text(self) -> None:
        self.assertEqual(
            clean_takeaway_description_prefix("Cost-effective decisions remain important."),
            "Cost-effective decisions remain important.",
        )

    def test_ai_keyword_tags_preserve_original_capitalization(self) -> None:
        segments = [
            {
                "template_id": "text",
                "content": {
                    "text_elements": [
                        {"template_id": "paragraph_large", "content": {"text": "Solar PV is expanding quickly."}}
                    ]
                },
            }
        ]

        tagged = apply_ai_keyword_tags(
            segments,
            entity_keywords={"solar pv"},
            prompts=["Explain {keyword}."],
        )

        text = tagged[0]["content"]["text_elements"][0]["content"]["text"]
        self.assertIn(">Solar PV 💬️</ai>", text)
        self.assertIn('prompt="Explain Solar PV."', text)

    def test_exact_triple_line_breaks_are_not_reported(self) -> None:
        issues = find_triple_line_break_issues(
            {
                "content": {
                    "text": "Before text.<br /><br /><br />After text."
                }
            }
        )
        self.assertEqual(issues, [])

    def test_four_plus_line_breaks_are_reported_with_context(self) -> None:
        issues = find_triple_line_break_issues(
            {
                "content": {
                    "text": "Before text.<br /><br /><br /><br />After text."
                }
            }
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("Before text.", issues[0]["message"])
        self.assertIn("After text.", issues[0]["message"])

    def test_trailing_four_plus_line_breaks_are_not_reported_after_normalization(self) -> None:
        issues = find_triple_line_break_issues(
            {
                "content": {
                    "body": "Before text.<br /><br /><br /><br />"
                }
            }
        )

        self.assertEqual(issues, [])

    def test_text_template_trims_outer_breaks_and_whitespace(self) -> None:
        node = DummyNode(
            name="body",
            node_type="TEXT",
            characters="  \n\nLeading and trailing text.\n\n  ",
        )

        value = ModuleText._extract_styled_text(node)

        self.assertEqual(value, "Leading and trailing text.")

    def test_text_template_collapses_exact_triple_break_to_double(self) -> None:
        node = DummyNode(
            name="body",
            node_type="TEXT",
            characters="First paragraph.\n\n\nSecond paragraph.",
        )

        value = ModuleText._extract_styled_text(node)

        self.assertEqual(value, "First paragraph.<br /><br />Second paragraph.")

    def test_text_template_preserves_four_plus_breaks_for_validation(self) -> None:
        node = DummyNode(
            name="body",
            node_type="TEXT",
            characters="First paragraph.\n\n\n\nSecond paragraph.",
        )

        value = ModuleText._extract_styled_text(node)

        self.assertEqual(value, "First paragraph.<br /><br /><br /><br />Second paragraph.")

    def test_validation_normalizer_strips_outer_breaks(self) -> None:
        value = normalize_text_for_line_break_validation("  <br /><br />Body text.<br /><br /><br /><br />  ")

        self.assertEqual(value, "Body text.")

    def test_partial_bullet_with_single_text_maps_to_body(self) -> None:
        group = DummyNode(
            name="bullet_point",
            node_type="GROUP",
            children=[
                DummyNode(name="text", node_type="TEXT", characters="Body-only bullet content."),
            ],
        )

        parsed = ModuleText._parse_group(group)

        self.assertEqual(parsed["template_id"], "bullet_point")
        self.assertEqual(parsed["content"]["title"], "")
        self.assertEqual(parsed["content"]["body"], "Body-only bullet content.")


if __name__ == "__main__":
    unittest.main()
