"""
Connection frames between different components.
"""

from pydantic import Field

from ..entities.components import Image
from ..entities.node import Node
from .base import FrameBase

__all__ = ["ConnectionNext"]


class ConnectionNext(FrameBase):
    """
    Next connection frame.
    """

    image: Image
    intro: str
    title: str
    cta: str = Field(default="Start learning")
    # next_lesson_id: str

    @classmethod
    def from_node(cls, node: Node) -> "ConnectionNext":
        """
        Create a ConnectionNext instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        ConnectionContent
            An instance of the ConnectionContent class populated with data from the node.
        """
        return cls(
            template_id="connection_next",
            image=Image.from_node(node.select_node("GROUP", "image")),
            intro=node.select_node("TEXT", "intro").characters,
            title=node.select_node("TEXT", "title").characters,
            cta=node.select_node("TEXT", "cta").characters,
        )
