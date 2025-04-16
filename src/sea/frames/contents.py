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
    "ListOfLessons",
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


class ModuleText(FrameBase):
    text_elements: list[dict]

    @classmethod
    def from_node(cls, node):
        assert node.name == "text", f"Expected text node, got {node.name}"

        raw_text_elements = []

        def infer_template_id(parent_name):
            text_template_ids = [
                "bullet_point",
                "bullet_point_with_highlight",
                "bullet_point_with_number",
                "kpi_highlight_large",
                "kpi_highlight_medium",
                "paragraph_large",
                "paragraph_medium",
                "paragraph_small",  # fallback
                "quote_large_with_name",
                "quote_large_without_name",
                "quote_small_with_name",
                "quote_small_without_name",
                "subtitle",
                "subtitle_small",
            ]
            name = parent_name.lower()
            for template in text_template_ids:
                if template in name:
                    return template
            return "paragraph_small"

        def walk(n, parent_name=None):
            if n.type == "TEXT" and n.characters and n.characters.strip():
                template_id = infer_template_id(parent_name or "")
                raw_text_elements.append(
                    {
                        "template_id": template_id,
                        "content": {"text": n.characters.strip()},
                    }
                )

            children = getattr(n, "children", None)
            if isinstance(children, list):
                for child in children:
                    walk(child, n.name if n.type != "TEXT" else parent_name)

        walk(node)

        return cls(template_id="text", text_elements=list(reversed(raw_text_elements)))

    def to_content(self) -> dict:
        return {
            "template_id": self.id,
            "colorscheme": self.colorscheme,
            "content": {"text_elements": self.text_elements},
        }


class LearningObjectives(FrameBase):
    """
    Learning objectives frame.
    """

    title: str
    intro: str
    objectives: list[Card]

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
        assert (
            node.name == "learning_objectives"
        ), f"Expected learning_objectives node, got {node.name}"
        return cls(
            template_id=node.name,
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            objectives=map(Card.from_node, node.select_nodes("GROUP", "objectives")),
        )


class KeyTakeaways(FrameBase):
    """
    Key takeaways frame.
    """

    title: str
    intro: str
    takeaways: list[Card]

    @classmethod
    def from_node(cls, node: Node) -> "KeyTakeaways":
        """
        Create a KeyTakeaways instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract key takeaways data.

        Returns
        -------
        KeyTakeaways
            An instance of the KeyTakeaways class populated with data from the node.
        """
        assert (
            node.name == "key_takeaways"
        ), f"Expected key_takeaways node, got {node.name}"
        return cls(
            template_id=node.name,
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            takeaways=map(Card.from_node, node.select_nodes("GROUP", "objectives")),
        )


class KeyResources(FrameBase):
    title: str
    intro: str
    resources: list[Card]

    @classmethod
    def from_node(cls, node: Node) -> "KeyResources":
        assert (
            node.name == "key_resources"
        ), f"Expected key_resources node, got {node.name}"
        return cls(
            template_id=node.name,
            title=node.select_node("TEXT", "title").characters,
            intro=node.select_node("TEXT", "intro").characters,
            resources=map(Card.from_node, node.select_nodes("GROUP", "resources")),
        )


class ListOfLessons(FrameBase):
    """
    Lesson overview frame.
    """

    title: str
    lessons: list[LessonThumbnail]

    @classmethod
    def from_node(cls, node: Node) -> "ListOfLessons":
        """
        Create a ListOfLessons instance from a Node object.

        Parameters
        ----------
        node : Node
            The Node object from which to extract content data.

        Returns
        -------
        ListOfLessons
            An instance of the ListOfLessons class populated with data from the node.
        """
        assert (
            node.name == "list_of_lessons"
        ), f"Expected list_of_lessons node, got {node.name}"
        return cls(
            template_id=node.name,
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
        assert (
            node.name == "key_concepts"
        ), f"Expected key_concepts node, got {node.name}"
        return cls(
            template_id=node.name,
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


class ScoredQuiz(FrameBase):
    quiz_data: dict

    @classmethod
    def from_node(cls, node: Node) -> "ScoredQuiz":
        assert node.name == "scored-quiz", f"Expected scored-quiz node, got {node.name}"
        quiz_data = node.to_dict() if hasattr(node, "to_dict") else {}
        return cls(
            template_id=node.name,
            quiz_data=quiz_data,
        )
