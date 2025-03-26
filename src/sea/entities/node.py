"""
Base node class defining shared properties for all nodes.
See https://www.figma.com/developers/api#files for details.
"""

from __future__ import annotations  # allow forward references

import re
from typing import Generator, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["NODE_TYPE", "Node"]

# As per https://www.figma.com/developers/api#node-types
NODE_TYPE = Literal[
    "DOCUMENT",
    "CANVAS",
    "FRAME",
    "GROUP",
    "SECTION",
    "VECTOR",
    "BOOLEAN_OPERATION",
    "STAR",
    "LINE",
    "ELLIPSE",
    "REGULAR_POLYGON",
    "RECTANGLE",
    "TABLE",
    "TABLE_CELL",
    "TEXT",
    "SLICE",
    "COMPONENT",
    "COMPONENT_SET",
    "INSTANCE",
    "STICKY",
    "SHAPE_WITH_TEXT",
    "CONNECTOR",
    "WASHI_TAPE",
]


class Node(BaseModel):
    """
    A generic node class that other nodes inherit from.

    The class defines shared properties that exist on every node.
    See https://www.figma.com/developers/api#global-properties.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(
        description="A string uniquely identifying this node within the document.",
    )
    name: str = Field(
        description="The name given to the node by the user in the tool.",
    )
    visible: bool = Field(
        default=True,
        description="Whether or not the node is visible on the canvas.",
    )
    type: NODE_TYPE = Field(
        description="The type of the node, refer to https://www.figma.com/developers/api#node-types for details."
    )
    rotation: float = Field(
        default=0.0,
        description="The rotation of the node, if not 0.",
    )
    children: list[Node] | None = Field(
        default=None,
        description="Descendant nodes if applicable.",
    )

    def select_nodes(
        self,
        type: NODE_TYPE,
        pattern: str = ".+",
        recursive: bool = True,
    ) -> Generator[Node, None, None]:
        """
        Select descendant nodes of a certain type whose names match a pattern.

        Parameters
        ----------
        type : NODE_TYPE
            Node type to filter.
        pattern : str, default=".+"
            Regex pattern to match against node names.
        recursive : bool, default=True
            If True, select all descendant nodes that match the criteria,
            otherwise only select from immediate descendants.

        Yields
        ------
        Node
            Matching nodes of a given type.
        """
        if self.visible and (children := self.children):
            # sort the nodes to present in the righ-to-left, top-to-bottom manner
            children = sorted(
                self.children,
                key=lambda node: (
                    node.model_dump().get("absoluteBoundingBox", {}).get("y", 0),
                    node.model_dump().get("absoluteBoundingBox", {}).get("x", 0),
                ),
            )
            for child in children:
                if child.type == type and re.search(pattern, child.name):
                    yield child
                if recursive:
                    yield from child.select_nodes(type, pattern, recursive)

    def select_node(
        self,
        node: Node,
        type: NODE_TYPE,
        pattern: str = ".+",
        recursive: bool = True,
    ) -> Node | None:
        """
        Select the first descendant node of a certain type whose name matches a pattern.

        Parameters
        ----------
        type : NODE_TYPE
            Node type to filter.
        pattern : str, default=".+"
            Regex pattern to match against node names.
        recursive : bool, default=True
            If True, select any descendant node that matches the criteria, otherwise,
            only select from immediate descendants.

        Returns
        -------
        Node or None
            The first matching node of a given type or None.
        """
        try:
            return next(self.select_nodes(node, type, pattern, recursive))
        except StopIteration:
            return None
