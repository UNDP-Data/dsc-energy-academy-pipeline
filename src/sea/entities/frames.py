"""
Individual frames to be converted to JSON templates.
"""

from typing import Literal

from pydantic import BaseModel, Field

from .components import Card, Concept, Image, Intro, LessonThumbnail, NextBlock
from .node import Node

__all__ = [
    "Cover",
    "ModuleText",
    "LearningObjectives",
    "ConnectionNext",
    "LessonOverview",
    "KeyConcepts",
    "PhotoVertical",
    "Quote",
    "ChapterOutro",
]


class Metadata(BaseModel):
    """
    Base metadata class all frames inherit from.
    """

    id: str = Field(alias="template_id")
    colorscheme: Literal["light", "dark"] | None = Field(default=None)


class Cover(Metadata):
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


class TextElement(Metadata):
    """
    Generic text element.
    """

    text: str

    @classmethod
    def from_node(cls, node: Node) -> "TextElement":
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
        return cls(
            template_id=node.name,
            text=node.select_node("TEXT", "text").characters,
        )


class ModuleText(Metadata):
    """
    Module text frame.
    """

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
        return cls(
            template_id="text",
            colorscheme="dark",
            content=map(TextElement.from_node, node.select_nodes("GROUP")),
        )


class LearningObjectives(Metadata):
    """
    Learning objectives frame, also used for key takeaways.
    """

    title: str
    intro: str
    cards: list[Card]  # use a generic name instead of objectives or takeaways

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
        assert node.name in {
            "learning_objectives",
            "key_takeaways",
        }, f"Node '{node.name}' is not supported"
        return cls(
            template_id=node.name,
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            cards=map(Card.from_node, node.select_nodes("GROUP", "objectives")),
        )


class ConnectionNext(Metadata):
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


class LessonOverview(Metadata):
    """
    Lesson overview frame.
    """

    title: str
    lessons: list[LessonThumbnail]

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
            template_id="list_of_lessons",
            title=node.select_node("TEXT", "title").characters,
            lessons=map(
                LessonThumbnail.from_node, node.select_nodes("GROUP", "lessons")
            ),
        )


class KeyConcepts(Metadata):
    """
    Key concepts frame.
    """

    title: str
    intro: str
    concepts: list[Concept]

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
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            concepts=map(Concept.from_node, node.select_nodes("GROUP", "concepts")),
        )


class PhotoVertical(Metadata):
    """
    Photo vertical frame.
    """

    image: Image

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
            image=Image.from_node(node),
        )


class Quote(Metadata):
    """
    Large quote with a name frame.
    """

    quote: str
    author: str

    @classmethod
    def from_node(cls, node: Node) -> "Quote":
        """
        Create a Quote instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        Quote
            An instance of the Quote class populated with data from the node.
        """
        assert node.name.startswith("quote_"), f"Expected a quote node, not {node.name}"
        return cls(
            template_id=node.name,
            quote=node.select_node("TEXT", "quote").characters,
            author=node.select_node("TEXT", "author").characters,
        )


class ChapterOutro(Metadata):
    """
    Chapter outro frame.
    """

    intro: str
    title: str
    subtitle: str
    body: str
    next_block: NextBlock

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
        title = " ".join(
            [
                node.select_node("TEXT", "first_line").characters,
                node.select_node("TEXT", "first_line").characters,
            ]
        )
        return cls(
            template_id="chapter_outro",
            intro=node.select_node("TEXT", "intro").characters,
            title=title,
            subtitle=node.select_node("TEXT", "subtitle").characters,
            body=node.select_node("TEXT", "body").characters,
            next_block=NextBlock.from_node(node.select_node("GROUP", "quiz")),
        )
