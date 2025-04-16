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

    src: str | None = None
    caption: str | None = None
    url: str | None = None

    @classmethod
    def from_node(cls, node: Node | None) -> "Image":
        """
        Create an Image instance from a Node object.

        Extract image properties from an image node assumed to be a group with children:
        - Look for a child whose type (case‑insensitive) is either "ATTR" or "RECTANGLE" and use its name as the image file name (src).
        - Look for a child with name "caption": its "characters" property holds the caption.

        Parameters
        ----------
        node : Node
            The Node object from which to extract image data.

        Returns
        -------
        Image
            An instance of the Image class populated with data from the node.
        """
        if node is None:
            return cls()

        for child in node.children:
            child_type = getattr(child, "type", "")
            child_name = getattr(child, "name", "")
            # Check for either ATTR or RECTANGLE type to get the image file name.
            if (
                child_type
                and child_type.upper() in ("ATTR", "RECTANGLE")
                and src_val is None
            ):
                src_val = child_name
            elif child_name == "caption":
                ##this is set to "" since most image captions are temp
                caption_val = ""  # getattr(child, "characters", None)

        return cls(src=src_val, caption=caption_val)


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
    description: str
    lesson_id: str = Field(alias="lessonId")
    image: Image
    title: str
    type: str = Field(default="Lesson")
    progress: Literal["completed", "in_progress", "not_started"] = Field(
        default="not_starterd"
    )

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

        lessonId = "1.1.1"  ## this needs to be patched
        description_node = node.select_node("TEXT", "description")
        return cls(
            title=node.select_node("TEXT", "title").characters,
            image=Image.from_node(node.select_node("GROUP", "image")),
            # progress=progress,
            lessonId=lessonId,
            cta="Go to the lesson",
            description=(
                description_node.characters if description_node is not None else ""
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


def parse_image_fields(node: Node) -> dict:
    """
    Extract image properties from an image node assumed to be a group with children:
      - Look for a child whose type (case‑insensitive) is either "ATTR" or "RECTANGLE" and use its name as the image file name (src).
      - Look for a child with name "caption": its "characters" property holds the caption.

    Debug prints are added to help trace the internal state.
    """
    if node is None:
        return {}

    src_val = None
    caption_val = None
    url_val = None  # Extend if needed

    children = getattr(node, "children", None)

    for child in list(children):
        child_type = getattr(child, "type", "")
        child_name = getattr(child, "name", "")
        # Check for either ATTR or RECTANGLE type to get the image file name.
        if (
            child_type
            and child_type.upper() in ("ATTR", "RECTANGLE")
            and src_val is None
        ):
            src_val = child_name
        elif child_name == "caption":
            ##this is set to "" since most image captions are temp
            caption_val = ""  # getattr(child, "characters", None)

    return {"src": src_val, "caption": caption_val}


# --- Helper for photo-horizontal images (direct extraction) ---
def parse_photo_horizontal_fields(node: Node) -> dict:
    """
    Extract image properties for photo-horizontal template.
    Assumes the node directly has an attribute "imageUrl".
    """
    if node is None:
        return {}
    image_url_node = node.select_node("ATTR", "imageUrl")
    image_url = image_url_node.value if image_url_node else None
    return {"src": image_url, "caption": None, "url": None}


def parse_cover_fields(node: Node) -> dict:
    intro_node = node.select_node("GROUP", "module|chapter|lesson")

    # Default to None
    intro_val = None
    intro_type = "intro"  # fallback key if type can't be inferred

    if intro_node:
        # Use the node name to determine the type (module/chapter/lesson)
        raw_name = intro_node.name.lower()
        if "module" in raw_name:
            intro_type = "module"
        elif "chapter" in raw_name:
            intro_type = "chapter"
        elif "lesson" in raw_name:
            intro_type = "lesson"
        else:
            intro_type = "intro"  # fallback

        intro_val = Intro.from_node(intro_node).model_dump()
    else:
        # Fallback to a text node labeled "intro"
        intro_val = node.select_node("TEXT", "intro").characters
        intro_type = "intro"

    image_node = node.select_node("GROUP", "image")
    image_val = parse_image_fields(image_node) if image_node else {}

    return {
        "template_id": node.name,
        "image": image_val,
        intro_type: intro_val,
        "title": node.select_node("TEXT", "title").characters,
        "cta": (
            node.select_node("TEXT", "cta").characters
            if node.select_node("TEXT", "cta") is not None
            else None
        ),
        "intro": "",
    }
