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


class ChapterOutro(FrameBase):
    intro: str
    title: str
    subtitle: str
    body: str
    nextBlock: dict

    @classmethod
    def from_node(cls, node: Node) -> "ChapterOutro":
        assert (
            node.name == "chapter_outro"
        ), f"Expected chapter_outro node, got {node.name}"
        nextBlock = NextBlock.from_node(node.select_node("GROUP", "quiz")).model_dump()
        nextBlock["nextBlockId"] = "1.1.5"
        return cls(
            template_id=node.name,
            intro=node.select_node("TEXT", "intro").characters,
            title="tmp",  # node.select_node("TEXT", "title").select_node("first_line").characters,
            subtitle=node.select_node("TEXT", "subtitle").characters,
            body="tmp",  # node.select_node("TEXT", "body").characters,
            nextBlock=nextBlock,
        )


class ModuleOutro(FrameBase):
    intro: str
    title: str
    subtitle: str
    body: str
    nextBlock: dict

    @classmethod
    def from_node(cls, node: Node) -> "ModuleOutro":
        assert (
            node.name == "module_outro"
        ), f"Expected module_outro node, got {node.name}"
        nextBlock = NextBlock.from_node(node.select_node("GROUP", "quiz")).model_dump()
        nextBlock["nextBlockId"] = "1.1.5"
        return cls(
            template_id=node.name,
            intro=node.select_node("TEXT", "intro").characters,
            title=node.select_node("TEXT", "title").characters,
            subtitle=node.select_node("TEXT", "subtitle").characters,
            body=node.select_node("TEXT", "body").characters,
            nextBlock=nextBlock,
        )
