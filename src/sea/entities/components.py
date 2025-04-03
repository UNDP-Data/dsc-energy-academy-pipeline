"""
Reusable components used to create frame templates.
"""

from pydantic import BaseModel, Field

from .node import Node

__all__ = [
    "Image",
    "Intro",
    "CoverContent",
    "TextConent",
    "Objective",
    "ObjectivesContent",
    "ConnectionContent",
]


class Image(BaseModel):
    """
    Generic image component.
    """

    src: str
    caption: str | None = None
    url: str | None = None

    @classmethod
    def from_node(cls, node: Node) -> "Image":
        """
        Create an Image instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract image data.

        Returns
        -------
        Image
            An instance of the Image class populated with data from the node.
        """
        return cls(
            src=node.select_node("RECTANGLE").name,
            caption=node.select_node("TEXT").characters,
        )


class Intro(BaseModel):
    """
    Generic component for a module, lesson or chapter intro.
    """

    label: str
    number: str

    @classmethod
    def from_node(cls, node: Node) -> "Intro":
        """
        Create an Intro instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract intro data.

        Returns
        -------
        Intro
            An instance of the Intro class populated with data from the node.
        """
        return cls(
            label=node.select_node("TEXT", "label").characters.title(),
            number=node.select_node("TEXT", "number").characters,
        )


class CoverContent(BaseModel):
    """
    Generic content component for a module, lesson or chapter cover.
    """

    image: Image
    intro: Intro
    title: str
    cta: str | None = Field(default="Scroll, tab or use your keyboard to move ahead")


class TextConent(BaseModel):
    """
    Generic content component for text.
    """

    text: str


class Objective(BaseModel):
    """
    Learning objective component.
    """

    image: Image
    title: str
    description: str

    @classmethod
    def from_node(cls, node: Node) -> "Objective":
        """
        Create an Objective instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract objective data.

        Returns
        -------
        Objective
            An instance of the Objective class populated with data from the node.
        """
        return cls(
            image=Image.from_node(node.select_node("GROUP", "image")),
            title=node.select_node("TEXT", "title").characters,
            description=node.select_node("TEXT", "description").characters,
        )


class ObjectivesContent(BaseModel):
    """
    Content component for learning objectives.
    """

    title: str
    intro: str
    objectives: list[Objective]

    @classmethod
    def from_node(cls, node: Node) -> "ObjectivesContent":
        """
        Create an ObjectivesContent instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        ObjectivesContent
            An instance of the ObjectivesContent class populated with data from the node.
        """
        objectives = list(
            map(Objective.from_node, node.select_nodes("GROUP", "objectives"))
        )

        return cls(
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            objectives=objectives,
        )


class ConnectionContent(BaseModel):
    image: Image
    intro: str
    title: str
    cta: str = Field(default="Start learning")
    # next_lesson_id: str

    @classmethod
    def from_node(cls, node: Node) -> "ConnectionContent":
        """
        Create an ConnectionContent instance from a Node object.

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
            image=Image.from_node(node.select_node("GROUP", "image")),
            intro=node.select_node("TEXT", "intro").characters,
            title=node.select_node("TEXT", "title").characters,
            cta=node.select_node("TEXT", "cta").characters,
        )
