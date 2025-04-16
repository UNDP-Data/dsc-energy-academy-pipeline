"""
Cover-related frames for a module, chapter, lesson or lesson part.
"""

from pydantic import Field

from ..nodes import Node
from .base import FrameBase
from .utils import Image, Intro, parse_cover_fields

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


class LessonCover(FrameBase):
    image: Image
    lesson: dict | str
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")
    intro: str

    @classmethod
    def from_node(cls, node: Node) -> "LessonCover":
        assert (
            node.name == "lesson_cover"
        ), f"Expected lesson_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        # Force immediate evaluation of image field.
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class ModuleCover(FrameBase):
    image: Image
    module: dict | str
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")
    intro: str

    @classmethod
    def from_node(cls, node: Node) -> "ModuleCover":
        assert (
            node.name == "module_cover"
        ), f"Expected module_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class LessonSubpartCover(FrameBase):
    image: Image
    intro: dict | str
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")

    @classmethod
    def from_node(cls, node: Node) -> "LessonSubpartCover":
        assert (
            node.name == "lesson_subpart_cover"
        ), f"Expected lesson_subpart_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class LessonPartCover(FrameBase):
    image: Image
    intro: dict | str
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")

    @classmethod
    def from_node(cls, node: Node) -> "LessonPartCover":
        assert (
            node.name == "lesson_part_cover"
        ), f"Expected lesson_part_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class ChapterCover(FrameBase):
    image: Image
    chapter: dict | str
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")
    intro: str

    @classmethod
    def from_node(cls, node: Node) -> "ChapterCover":
        assert (
            node.name == "chapter_cover"
        ), f"Expected chapter_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)
