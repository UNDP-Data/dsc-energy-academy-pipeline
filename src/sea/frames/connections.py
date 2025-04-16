"""
Connection frames between different components.
"""

from pydantic import Field

from ..nodes import Node
from .base import FrameBase
from .utils import Image

__all__ = ["ConnectionNext", "ConnectionBack"]


class ConnectionNext(FrameBase):
    """
    Next connection frame.
    """

    image: Image
    intro: str
    title: str
    cta: str = Field(default="Start learning")
    next_lesson_id: str = Field(alias="nextLessonId")

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
        assert (
            node.name == "connection_next"
        ), f"Expected connection_next node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        return cls(
            template_id=node.name,
            image=image_node,
            intro=node.select_node("TEXT", "intro").characters,
            title=node.select_node("TEXT", "title").characters,
            cta=node.select_node("TEXT", "cta").characters,
            next_lesson_id="1.1.1",
        )


class ConnectionBack(FrameBase):
    image: Image
    intro: str
    title: str
    cta: str | None = None

    @classmethod
    def from_node(cls, node: Node) -> "ConnectionBack":
        assert (
            node.name == "connection_back"
        ), f"Expected connection_back node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        cta_node = node.select_node("TEXT", "cta")
        return cls(
            template_id=node.name,
            image=Image.from_node(image_node),
            intro=node.select_node("TEXT", "intro").characters,
            title=node.select_node("TEXT", "title").characters,
            cta=(cta_node.characters if cta_node is not None else None),
        )
