"""
Document node type. See https://www.figma.com/developers/api#node-types.
"""

import os

import requests

from .node import Node

__all__ = ["Document"]


class Document(Node):
    """
    Document node type that can be instantiated from a Figma file key.
    """

    metadata: dict

    @classmethod
    def from_file_key(cls, key: str) -> "Document":
        """
        Factory class to create a document instance from a Figma file key.

        Parameters
        ----------
        key : str
            A file key to export JSON from.

        Returns
        -------
        dict
            Node of type DOCUMENT as a JSON object.
        """
        endpoint = f"https://api.figma.com/v1/files/{key}"
        headers = {"X-Figma-Token": os.environ["FIGMA_API_KEY"]}
        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        document = data.pop("document")
        parsed_document = cls(**document, metadata=data)
        parsed_document.report_text_path_nodes(label=f"Downloaded Figma file {key}")
        return parsed_document

    def report_text_path_nodes(self, label: str = "Figma document") -> list[dict[str, str]]:
        """
        Print cleanup targets for unsupported text-on-path nodes in Figma.
        """
        matches = self.find_nodes_by_type("TEXT_PATH")
        if not matches:
            return matches

        print(f"⚠️ TEXT_PATH nodes found in {label}: {len(matches)}")
        print("   These are text-on-path objects. Convert/replace them in Figma if they should not be in the pipeline.")
        for match in matches:
            print(
                f"   - id={match['id']} | name={match['name']} | diagnostics={match['diagnostics'] or 'none'} | "
                f"visible={match['visible']} | render_bounds={match['absoluteRenderBounds']} | "
                f"box={match['absoluteBoundingBox']} | path={match['path']}"
            )
        return matches
