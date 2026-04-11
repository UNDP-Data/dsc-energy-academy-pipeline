from __future__ import annotations

import sys
import unittest
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from entities.frames import Infographic


class DummyNode:
    def __init__(
        self,
        *,
        name: str,
        node_type: str,
        node_id: str = "node-id",
        children: list["DummyNode"] | None = None,
        characters: str = "",
        width: float = 1400,
    ) -> None:
        self.name = name
        self.type = node_type
        self.id = node_id
        self.children = children or []
        self.characters = characters
        self.absoluteBoundingBox = {"width": width}


class InfographicFrameTests(unittest.TestCase):
    def test_infographic_uses_single_child_frame_regardless_of_name(self) -> None:
        design = DummyNode(name="some-random-name", node_type="FRAME", node_id="123:456")
        title = DummyNode(name="title", node_type="TEXT", characters="Grid overview")
        node = DummyNode(
            name="infographic",
            node_type="FRAME",
            node_id="wrapper:1",
            children=[design, title],
        )

        frame = Infographic.from_node(node)

        self.assertEqual(frame.image["src"], "123:456")
        self.assertEqual(frame.metadata["title"], "Grid overview")

    def test_infographic_raises_when_child_frame_count_is_not_exactly_one(self) -> None:
        first = DummyNode(name="design-a", node_type="FRAME", node_id="123:1")
        second = DummyNode(name="design-b", node_type="FRAME", node_id="123:2")
        node = DummyNode(
            name="infographic",
            node_type="FRAME",
            node_id="wrapper:2",
            children=[first, second],
        )

        with self.assertRaisesRegex(ValueError, r"exactly 1 child FRAME, found 2"):
            Infographic.from_node(node)


if __name__ == "__main__":
    unittest.main()
