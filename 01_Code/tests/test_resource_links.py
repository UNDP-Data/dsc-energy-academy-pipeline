from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from sea_pipeline.core.resource_links import load_resource_lessons_df, resolve_resource_href


class ResourceLinkTests(unittest.TestCase):
    def test_resolve_resource_href_prefers_link_column(self) -> None:
        row = pd.Series({"Link": "https://example.com/new", "Resource Link": "https://example.com/old"})
        self.assertEqual(resolve_resource_href(row), "https://example.com/new")

    def test_resolve_resource_href_falls_back_to_resource_link(self) -> None:
        row = pd.Series({"Link": "", "Resource Link": "https://example.com/fallback"})
        self.assertEqual(resolve_resource_href(row), "https://example.com/fallback")

    def test_resolve_resource_href_uses_resource_source_when_columns_are_swapped(self) -> None:
        row = pd.Series(
            {
                "Resource Link": "UNWOMEN",
                "Resource Source": "https://example.com/actual-link",
            }
        )
        self.assertEqual(resolve_resource_href(row), "https://example.com/actual-link")

    def test_resolve_resource_href_still_prefers_resource_link_when_it_is_the_url(self) -> None:
        row = pd.Series(
            {
                "Resource Link": "https://example.com/resource-link",
                "Resource Source": "UNWOMEN",
            }
        )
        self.assertEqual(resolve_resource_href(row), "https://example.com/resource-link")

    def test_load_resource_lessons_df_prefers_workbook_and_falls_back_to_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workbook_path = root / "SEA Table of Contents.xlsx"
            csv_path = root / "sea-lessons.csv"

            csv_df = pd.DataFrame([{"Lesson Number": "1.1.1", "Link": "https://csv.example"}])
            csv_df.to_csv(csv_path, index=False)

            loaded = load_resource_lessons_df(workbook_path, csv_path)
            self.assertEqual(loaded.iloc[0]["Link"], "https://csv.example")

            workbook_df = pd.DataFrame([{"Lesson Number": "1.1.1", "Link": "https://xlsx.example"}])
            workbook_df.to_excel(workbook_path, sheet_name="Lessons", index=False)

            loaded = load_resource_lessons_df(workbook_path, csv_path)
            self.assertEqual(loaded.iloc[0]["Link"], "https://xlsx.example")


if __name__ == "__main__":
    unittest.main()
