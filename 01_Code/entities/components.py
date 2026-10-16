"""
Reusable components used to create frame templates.
"""

from typing import Literal
import re

from pydantic import BaseModel, Field

from .node import Node

__all__ = ["Image", "Intro", "Card", "LessonThumbnail", "Concept"]


def normalize_plain_text_value(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"^(?:\s*<br\s*/?>\s*)+|(?:\s*<br\s*/?>\s*)+$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:(?:\r\n|\r|\n)\s*){3,}", lambda m: "\n\n" if len(re.findall(r"\r\n|\r|\n", m.group(0))) == 3 else m.group(0), cleaned)
    cleaned = re.sub(r"(?:(?:<br\s*/?>\s*){3,})", lambda m: "<br /><br />" if len(re.findall(r"<br\s*/?>", m.group(0), flags=re.IGNORECASE)) == 3 else m.group(0), cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def split_first_sentence(text: str) -> tuple[str, str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return "", ""

    match = re.match(r"(.+?[.!?])(?:\s+|$)(.*)", cleaned, flags=re.DOTALL)
    if not match:
        return cleaned, ""

    title = match.group(1).strip()
    description = match.group(2).strip()
    return title, description


def clean_takeaway_description_prefix(description: str) -> str:
    """Remove stray standalone dash artifacts after the first takeaway sentence."""
    return re.sub(r"^\s*[-–—]\s+", "", description or "").strip()


def safe_get_characters(node: Node, field: str, template_id: str, default: str = "") -> str:
    selected = node.select_node("TEXT", field)
    if selected is None:
        if field not in ["cta","caption"]:
            print(f"⚠️ Missing field '{field}' in template '{template_id}'")
        return default
    try:
        return normalize_plain_text_value(selected.characters)
    except Exception as e:
        print(f"❌ Error getting '.characters' for field '{field}' in template '{template_id}': {e}")
        return default

class Image(BaseModel):
    """
    Generic image component.
    """

    src: str
    caption: str | None = None

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
            src=node.select_node("RECTANGLE").id,
            caption = safe_get_characters(node, "caption", node.name)
            
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
            label=safe_get_characters(node, "label", node.name).title(),
            number=safe_get_characters(node, "number", node.name)
        )


class Card(BaseModel):
    """
    Card component used in learning objectives and key takeaways.
    """

    image: Image
    title: str
    description: str

    @classmethod
    def from_node(cls, node: Node, *, split_title_from_description: bool = False) -> "Card":
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
        #print(node)

        try:##description here is separated because it is optional only for takeaways
            description=node.select_node("TEXT", "description").characters
        except:
            description=""

        title = safe_get_characters(node, "title", node.name)
        if split_title_from_description and title and not str(description).strip():
            title, description = split_first_sentence(title)
            description = clean_takeaway_description_prefix(description)

        return cls(
            image=Image.from_node(node.select_node("GROUP", "image")),
            title=title,
            description=description
        )



class LessonThumbnail(BaseModel):
    """
    Lesson thumbnail component for a list of lessons.
    """

    cta: str = Field(default="Go to the lesson")
    description: str
    lessonId: str = Field(alias='lessonId')
    image: Image
    title: str
    type: str
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
        
        progress = "not_started"
        type = "Lesson"
        lessonId="1.1.1"## this needs to be patched

        return cls(
            title=safe_get_characters(node, "title", node.name),
            image=Image.from_node(node.select_node("GROUP", "image")),
            progress=progress,
            lessonId=lessonId,
            type=type,
            cta="Go to the lesson",
            description=safe_get_characters(node, "description", node.name),
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
            body=safe_get_characters(node, "body", node.name),
            title=safe_get_characters(node, "title", node.name),
            source=safe_get_characters(node, "source", node.name)
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
            intro=safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            cta=safe_get_characters(node, "cta", node.name),
            button_cta=safe_get_characters(node, "buttonCta", node.name),
            image=Image.from_node(node.select_node("GROUP", "image")),
        )
