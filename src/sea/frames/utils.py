"""
Reusable utility components used to create frame templates.
"""

from typing import Literal

from pydantic import BaseModel, Field

from ..nodes import Node

__all__ = ["Image", "Intro", "Card", "LessonThumbnail", "Concept"]


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


class Card(BaseModel):
    """
    Card component used in learning objectives and key takeaways.
    """

    image: Image
    title: str
    description: str

    @classmethod
    def from_node(cls, node: Node) -> "Card":
        """
        Create a Card instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract objective data.

        Returns
        -------
        Card
            An instance of the Card class populated with data from the node.
        """
        title_node = node.select_node("TEXT", "title")
        description_node = node.select_node("TEXT", "description")
        return cls(
            image=Image.from_node(node.select_node("GROUP", "image")),
            title=title_node.characters if title_node is not None else "",
            description=(
                description_node.characters if description_node is not None else ""
            ),
        )


class LessonThumbnail(BaseModel):
    """
    Lesson thumbnail component for a list of lessons.
    """

    cta: str = Field(default="Go to the lesson")
    # description: str
    # sequence_id: str = Field(alias='lessonId')
    image: Image
    title: str
    # type: str
    progress: Literal["completed", "in_progress", "not_started"]

    @classmethod
    def from_node(cls, node: Node) -> "LessonThumbnail":
        """
        Create an LessonThumbnail instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        LessonThumbnail
            An instance of the LessonThumbnail class populated with data from the node.
        """
        if node.select_node("RECTANGLE", "progress") is None:
            progress = "not_started"
        # elif ...:
        #     progress = "in_progress"
        else:
            progress = "completed"
        return cls(
            title=node.select_node("TEXT", "title").characters,
            image=Image.from_node(node.select_node("GROUP", "image")),
            progress=progress,
        )


class Concept(BaseModel):
    """
    Concept component for key concepts frame.
    """

    title: str
    body: str
    source: str | None

    @classmethod
    def from_node(cls, node: Node) -> "Concept":
        """
        Create an Concept instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        Concept
            An instance of the Concept class populated with data from the node.
        """
        return cls(
            title=node.select_node("TEXT", "title").characters,
            body=node.select_node("TEXT", "body").characters,
            # parse cta if it is available, otherwise, use None
            source=(
                source.characters
                if (source := node.select_node("TEXT", "source")) is not None
                else None
            ),
        )


class NextBlock(BaseModel):
    """
    Next block component for chapter outro.
    """

    intro: str
    title: str
    cta: str
    button_cta: str
    image: Image
    # next_block_id: str

    @classmethod
    def from_node(cls, node: Node) -> "NextBlock":
        """
        Create an NextBlock instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        NextBlock
            An instance of the NextBlock class populated with data from the node.
        """
        return cls(
            intro=node.select_node("TEXT", "intro").characters,
            title=node.select_node("TEXT", "title").characters,
            cta=node.select_node("TEXT", "cta").characters,
            button_cta=node.select_node("TEXT", "buttonCta").characters,
            image=Image.from_node(node.select_node("GROUP", "image")),
        )
