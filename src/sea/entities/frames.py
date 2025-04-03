"""
Individual frames to be converted to JSON templates.
"""

from typing import Literal

from pydantic import BaseModel, Field

from .components import (
    ConnectionContent,
    CoverContent,
    Image,
    ImageContent,
    Intro,
    KeyConceptsContent,
    ObjectivesContent,
    OutroContent,
    OverviewContent,
    QuoteContent,
    TextConent,
)
from .node import Node

__all__ = [
    "ModuleCover",
    "ModuleText",
    "LearningObjectives",
    "ConnectionNext",
    "LessonOverview",
    "KeyConcepts",
    "PhotoVertical",
    "QuoteLargeWithName",
    "ChapterOutro",
]


class Metadata(BaseModel):
    """
    Base metadata class all frames inherit from.
    """

    id: str = Field(alias="template_id")


class ModuleCover(Metadata):
    """
    Module cover frame.
    """

    content: CoverContent

    @classmethod
    def from_node(cls, node: Node) -> "ModuleCover":
        """
        Create a ModuleCover instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract module cover data.

        Returns
        -------
        ModuleCover
            An instance of the ModuleCover class populated with data from the node.
        """
        # parse the image
        image_node = node.select_node("GROUP", "image")
        image = Image.from_node(image_node)
        # parse the intro
        if (module_node := node.select_node("GROUP", "module|chapter|lesson")) is None:
            # handle lesson_part_cover that uses a single string instead
            intro = node.select_node("TEXT", "intro").characters
        else:
            intro = Intro.from_node(module_node)
        # create the content
        content = CoverContent(
            image=image,
            intro=intro,
            title=node.select_node("TEXT", "title").characters,
            # parse cta if it is available, otherwise, use None
            cta=(
                cta.characters
                if (cta := node.select_node("TEXT", "cta")) is not None
                else None
            ),
        )
        return cls(template_id="module_cover", content=content)


class TextElement(Metadata):
    """
    Generic text element.
    """

    content: TextConent

    @classmethod
    def from_node(cls, node: Node) -> "Intro":
        """
        Create a TextElement instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract text element data.

        Returns
        -------
        TextElement
            An instance of the TextElement class populated with data from the node.
        """
        content = TextConent(text=node.select_node("TEXT", "text").characters)
        return cls(template_id=node.name, content=content)


class ModuleText(Metadata):
    """
    Module text frame.
    """

    colorscheme: Literal["light", "dark"]
    content: list[TextElement]

    @classmethod
    def from_node(cls, node: Node) -> "ModuleText":
        """
        Create a ModuleText instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract module text data.

        Returns
        -------
        ModuleText
            An instance of the ModuleText class populated with data from the node.
        """
        content = list(map(TextElement.from_node, node.select_nodes("GROUP")))
        return cls(template_id="text", colorscheme="dark", content=content)


class LearningObjectives(Metadata):
    """
    Learning objectives frame.
    """

    content: ObjectivesContent

    @classmethod
    def from_node(cls, node: Node) -> "LearningObjectives":
        """
        Create a LearningObjectives instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract learning objectives data.

        Returns
        -------
        LearningObjectives
            An instance of the LearningObjectives class populated with data from the node.
        """
        return cls(
            template_id="learning_objectives",
            content=ObjectivesContent.from_node(node),
        )


class ConnectionNext(Metadata):
    """
    Next connection frame.
    """

    content: ConnectionContent

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
            content=ConnectionContent.from_node(node),
        )


class LessonOverview(Metadata):
    """
    Lesson overview frame.
    """

    content: OverviewContent

    @classmethod
    def from_node(cls, node: Node) -> "LessonOverview":
        """
        Create a LessonOverview instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        LessonOverview
            An instance of the LessonOverview class populated with data from the node.
        """
        return cls(
            template_id="connection_next",
            content=OverviewContent.from_node(node),
        )


class KeyConcepts(Metadata):
    """
    Key concepts frame.
    """

    colorscheme: Literal["light", "dark"]
    content: KeyConceptsContent

    @classmethod
    def from_node(cls, node: Node) -> "KeyConcepts":
        """
        Create a KeyConcepts instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        KeyConcepts
            An instance of the KeyConcepts class populated with data from the node.
        """
        return cls(
            template_id="key_concepts",
            colorscheme="dark",
            content=KeyConceptsContent.from_node(node),
        )


class PhotoVertical(Metadata):
    """
    Photo vertical frame.
    """

    colorscheme: Literal["light", "dark"]
    content: ImageContent

    @classmethod
    def from_node(cls, node: Node) -> "PhotoVertical":
        """
        Create a PhotoVertical instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        PhotoVertical
            An instance of the PhotoVertical class populated with data from the node.
        """
        return cls(
            template_id="photo_vertical",
            colorscheme="light",
            content=ImageContent.from_node(node),
        )


class QuoteLargeWithName(Metadata):
    """
    Large quote with a name frame.
    """

    content: QuoteContent

    @classmethod
    def from_node(cls, node: Node) -> "QuoteLargeWithName":
        """
        Create a QuoteLargeWithName instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        QuoteLargeWithName
            An instance of the QuoteLargeWithName class populated with data from the node.
        """
        return cls(
            template_id="quote_large_with_name",
            content=QuoteContent.from_node(node),
        )


class ChapterOutro(Metadata):
    """
    Chapter outro frame.
    """

    content: OutroContent

    @classmethod
    def from_node(cls, node: Node) -> "ChapterOutro":
        """
        Create a ChapterOutro instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        ChapterOutro
            An instance of the ChapterOutro class populated with data from the node.
        """
        return cls(
            template_id="chapter_outro",
            content=OutroContent.from_node(node),
        )
