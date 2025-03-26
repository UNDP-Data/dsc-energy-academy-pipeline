"""
Base node class defining shared properties for all nodes.
See https://www.figma.com/developers/api#files for details.
"""

from typing import Literal

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
    children: list["Node"] | None = Field(
        default=None,
        description="Descendant nodes if applicable.",
    )
