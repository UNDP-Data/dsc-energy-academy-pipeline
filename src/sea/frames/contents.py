"""
Content-related frames for modules, lessons and lesson parts.
"""

from ..nodes import Node
from .base import FrameBase
from .utils import Card, Concept, LessonThumbnail

__all__ = [
    "TextElement",
    "ModuleText",
    "LearningObjectives",
    "LessonOverview",
    "KeyConcepts",
    "Quote",
]


class TextElement(FrameBase):
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


class ModuleText(FrameBase):
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


class LearningObjectives(FrameBase):
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


class LessonOverview(FrameBase):
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


class KeyConcepts(FrameBase):
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


class Quote(FrameBase):
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
