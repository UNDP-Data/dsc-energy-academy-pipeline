from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from entities.document import Document


class EntityNodeTests(unittest.TestCase):
    def test_document_accepts_text_path_nodes_from_figma(self) -> None:
        document = Document(
            id="0:0",
            name="Document",
            type="DOCUMENT",
            metadata={},
            children=[
                {
                    "id": "1:1",
                    "name": "Page",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "2:1",
                            "name": "Curved text",
                            "type": "TEXT_PATH",
                        }
                    ],
                }
            ],
        )

        self.assertEqual(document.children[0].children[0].type, "TEXT_PATH")

    def test_document_reports_text_path_locations(self) -> None:
        document = Document(
            id="0:0",
            name="Document",
            type="DOCUMENT",
            metadata={},
            children=[
                {
                    "id": "1:1",
                    "name": "Module 1",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "2:1",
                            "name": "Curved text",
                            "type": "TEXT_PATH",
                        }
                    ],
                }
            ],
        )

        with patch("builtins.print") as mocked_print:
            matches = document.report_text_path_nodes(label="Test file")

        self.assertEqual(matches[0]["id"], "2:1")
        printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list)
        self.assertIn("TEXT_PATH nodes found in Test file: 1", printed)
        self.assertIn("diagnostics=empty_text, no_render_bounds", printed)
        self.assertIn('CANVAS "Module 1" (1:1)', printed)
        self.assertIn('TEXT_PATH "Curved text" (2:1)', printed)


if __name__ == "__main__":
    unittest.main()
