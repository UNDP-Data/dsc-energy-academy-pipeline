"""
Reusable components used to create frame templates.
"""

from typing import Literal

from pydantic import BaseModel, Field

from .node import Node

__all__ = [
    "Image",
    "ImageContent",
    "Intro",
    "CoverContent",
    "TextConent",
    "Objective",
    "ObjectivesContent",
    "ConnectionContent",
    "OverviewContent",
    "KeyConceptsContent",
    "QuoteContent",
    "OutroContent",
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


class ImageContent(BaseModel):
    """
    Image-only content
    """

    image: Image

    @classmethod
    def from_node(cls, node: Node) -> "Image":
        """
        Create an ImageContent instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract image data.

        Returns
        -------
        ImageContent
            An instance of the ImageContent class populated with data from the node.
        """
        return cls(image=Image.from_node(node))


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
    intro: Intro | str
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
    """
    Generic connection content.
    """

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


class OverviewContent(BaseModel):
    """
    Content component for a list of lessons.
    """

    title: str
    lessons: list[LessonThumbnail]

    @classmethod
    def from_node(cls, node: Node) -> "OverviewContent":
        """
        Create an OverviewContent instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        OverviewContent
            An instance of the OverviewContent class populated with data from the node.
        """
        return cls(
            title=node.select_node("TEXT", "title").characters,
            lessons=map(
                LessonThumbnail.from_node, node.select_nodes("GROUP", "lessons")
            ),
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


class KeyConceptsContent(BaseModel):
    """
    Content component for key concepts.
    """

    title: str
    intro: str
    concepts: list[Concept]

    @classmethod
    def from_node(cls, node: Node) -> "KeyConceptsContent":
        """
        Create an KeyConceptsContent instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        KeyConceptsContent
            An instance of the KeyConceptsContent class populated with data from the node.
        """
        return cls(
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            concepts=map(Concept.from_node, node.select_nodes("GROUP", "concepts")),
        )


class QuoteContent(BaseModel):
    """
    Generic quote component.
    """

    quote: str
    author: str

    @classmethod
    def from_node(cls, node: Node) -> "QuoteContent":
        """
        Create an QuoteContent instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        QuoteContent
            An instance of the QuoteContent class populated with data from the node.
        """
        return cls(
            quote=node.select_node("TEXT", "quote").characters,
            author=node.select_node("TEXT", "author").characters,
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


class OutroContent(BaseModel):
    """
    Content component for chapter outro.
    """

    intro: str
    title: str
    subtitle: str
    body: str
    next_block: NextBlock

    @classmethod
    def from_node(cls, node: Node) -> "OutroContent":
        """
        Create an OutroContent instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        OutroContent
            An instance of the OutroContent class populated with data from the node.
        """
        title = " ".join(
            [
                node.select_node("TEXT", "first_line").characters,
                node.select_node("TEXT", "first_line").characters,
            ]
        )
        return cls(
            intro=node.select_node("TEXT", "intro").characters,
            title=title,
            subtitle=node.select_node("TEXT", "subtitle").characters,
            body=node.select_node("TEXT", "body").characters,
            next_block=NextBlock.from_node(node.select_node("GROUP", "quiz")),
        )
