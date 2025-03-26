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
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        document = data.pop("document")
        return cls(**document, metadata=data)
