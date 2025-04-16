"""
Cover-related frames for a module, chapter, lesson or lesson part.
"""

from pydantic import Field

from ..components import Image, Intro
from ..nodes import Node
from .base import FrameBase

__all__ = ["Cover"]


class Cover(FrameBase):
    """
    Cover frame for a module, chapter, lesson or lesson part.
    """

    image: Image
    intro: Intro | str
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")

    @classmethod
    def from_node(cls, node: Node) -> "Cover":
        """
        Create a Cover instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract module cover data.

        Returns
        -------
        Cover
            An instance of the Cover class populated with data from the node.
        """
        assert node.name.endswith("_cover"), f"Expected a cover node, not {node.name}"
        # parse the intro
        if (module_node := node.select_node("GROUP", "module|chapter|lesson")) is None:
            # handle lesson_part_cover that uses a single string instead
            intro = node.select_node("TEXT", "intro").characters
        else:
            intro = Intro.from_node(module_node)
        return cls(
            template_id=node.name,
            image=Image.from_node(node.select_node("GROUP", "image")),
            intro=intro,
            title=node.select_node("TEXT", "title").characters,
            # parse cta if it is available, otherwise, use None
            cta=(
                cta.characters
                if (cta := node.select_node("TEXT", "cta")) is not None
                else None
            ),
        )
