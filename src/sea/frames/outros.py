"""
Outro-related frames.
"""

from ..nodes import Node
from .base import FrameBase
from .utils import NextBlock

__all__ = ["Outro"]


class Outro(FrameBase):
    """
    Outro frame for a module or chapter.
    """

    intro: str
    title: str
    subtitle: str
    body: str
    next_block: NextBlock

    @classmethod
    def from_node(cls, node: Node) -> "Outro":
        """
        Create a Outro instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        Outro
            An instance of the Outro class populated with data from the node.
        """
        assert node.name.endswith("_outro"), f"Expected an outro node, not {node.name}"
        title = " ".join(
            [
                node.select_node("TEXT", "first_line").characters,
                node.select_node("TEXT", "first_line").characters,
            ]
        )
        return cls(
            template_id=node.name,
            intro=node.select_node("TEXT", "intro").characters,
            title=title,
            subtitle=node.select_node("TEXT", "subtitle").characters,
            body=node.select_node("TEXT", "body").characters,
            next_block=NextBlock.from_node(node.select_node("GROUP", "quiz")),
        )
