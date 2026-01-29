"""
Individual frames to be converted to JSON templates.

This file defines only the frame classes specified in raw_frame_class_map:
  - LessonCover
  - ModuleCover
  - ConnectionNext
  - KeyConcepts
  - LearningObjectives
  - ListOfLessons
  - PhotoVertical
  - PhotoHorizontal
  - PhotoFullHeight
  - Video
  - ModuleText
  - LessonSubpartCover
  - LessonPartCover
  - CaseStudyCover
  - ChapterOutro
  - ModuleOutro
  - ConnectionBack
  - KeyTakeaways
  - KeyResources
  - ScoredQuiz
  - ImageHotspot
  - ChapterCover
  - Chart
  - Infographic
  - Embed
  - Poll
"""

from typing import Literal, List, Union, Dict
from pydantic import BaseModel, Field
import json
from pathlib import Path
from typing import ClassVar
from .components import Card, Concept, Intro, LessonThumbnail, NextBlock
from .node import Node
import requests
import re as _re
import pandas as _pd

__all__ = [
    "LessonCover",
    "ModuleCover",
    "ConnectionNext",
    "KeyConcepts",
    "LearningObjectives",
    "ListOfLessons",
    "PhotoVertical",
    "PhotoHorizontal",
    "PhotoFullHeight",
    "Video",
    "ModuleText",
    "LessonSubpartCover",
    "LessonPartCover",
    "CaseStudyCover",
    "ChapterOutro",
    "ModuleOutro",
    "ConnectionBack",
    "KeyTakeaways",
    "KeyResources",
    "ImageHotspot",
    "ChapterCover",
    "Chart",
    "Infographic",
    "Embed",
    "Poll"
]


class FrameBase(BaseModel):
    """
    Base class for all frames.
    This version builds the final output dictionary manually (preserving field order)
    by iterating over the fields in the order they were declared.
    """
    id: str = Field(alias="template_id")
    color_scheme: Literal["light", "dark"] | None = Field(default=None)

    def to_content(self) -> dict:
        meta = {
            "template_id": self.id,
            "color_scheme": self.color_scheme,
            **({"size": self.size} if hasattr(self, "size") else {})
        }

        content = {}
        for field in self.__fields__:
            if field in {"template_id", "color_scheme", "id", "size"}:
                continue
            value = getattr(self, field)
            content[field] = self._serialize_value(value)

        meta["content"] = content
        return meta


    def _serialize_value(self, value):
        if isinstance(value, BaseModel):
            # Recursively dump nested Pydantic models.
            return value.to_content() if hasattr(value, "to_content") else value.model_dump()
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            new_dict = {}
            for k, v in value.items():
                new_dict[k] = self._serialize_value(v)
            return new_dict
        else:
            return value

def safe_get_characters(node: Node, field: str, template_id: str, default: str = "") -> str:
    selected = node.select_node("TEXT", field)

    # Define suppressions as (template_id, field) or wildcarded
    suppress_warning = (
        (template_id == "photo-vertical" and field == "caption")
        or field == "cta"  # globally suppress cta warnings
        or template_id == "photo-horizontal"
    )

    if selected is None:
        if not suppress_warning:
            print(f"⚠️ Missing field '{field}' in template '{template_id}'")
        return default

    try:
        return selected.characters
    except Exception as e:
        if not suppress_warning:
            print(f"❌ Error getting '.characters' for field '{field}' in template '{template_id}': {e}")
        return default


def parse_image_fields(node: Node) -> dict:
    """
    Extract image properties from an image group node by selecting the first RECTANGLE
    that has a fill of type IMAGE. This avoids mistakenly selecting non-image rectangles.
    """
    if node is None:
        return {}

    src_val = None
    caption_val = ""

    children = getattr(node, "children", [])

    for child in children:
        if getattr(child, "type", "") == "RECTANGLE":
            fills = getattr(child, "fills", [])
            if isinstance(fills, list):
                for fill in fills:
                    if isinstance(fill, dict) and fill.get("type") == "IMAGE":
                        src_val = child.id
                        break
            if src_val:
                break

    for child in children:
        if getattr(child, "name", "") == "caption":
            caption_val = ""  # default blank, or use child.characters if needed
            break

    return {
        "src": src_val,
        "caption": caption_val
    }




def parse_cover_fields(node: Node) -> dict:
    
    
    image_node = node.select_node("GROUP", "image")
    image_val = parse_image_fields(image_node) if image_node else {}

    
    coverNode={
        "template_id": node.name,
        "image": image_val,
        "title":safe_get_characters(node, "title", node.name),
        "subtitle": (
            safe_get_characters(node, "subtitle", node.name)
            if node.name == "case_study_cover" else None
        ),
        "cta":safe_get_characters(node, "cta", node.name)
    }
    
    header_node = node.select_node("GROUP", "module|chapter|lesson")
    
    # Default to None
    header_val = None

    header_type = None

    if header_node:
        # Use the node name to determine the type (module/chapter/lesson)
        raw_name = header_node.name.lower()
        if "module" in raw_name:
            header_type = "module"
        elif "chapter" in raw_name:
            header_type = "chapter"
        elif "lesson" in raw_name:
            header_type = "lesson"
        else:
            header_type = "intro"  # fallback

        header_val = Intro.from_node(header_node).model_dump()
        coverNode[header_type]= header_val

    if header_type != "module":
        coverNode["intro"]=safe_get_characters(node, "intro", node.name)

        
    return coverNode




# --- Cover Frames ---
class LessonCover(FrameBase):
    image: dict
    lesson: Union[dict, str]
    title: str
    cta: Union[str, None] = Field(default="Scroll, tab or use your keyboard to move ahead")
    intro: str


    @classmethod
    def from_node(cls, node: Node) -> "LessonCover":
        assert node.name == "lesson_cover", f"Expected lesson_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        # Force immediate evaluation of image field.
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class ModuleCover(FrameBase):
    image: dict
    module: Union[dict, str]
    title: str
    cta: Union[str, None] = Field(default="Scroll, tab or use your keyboard to move ahead")

    @classmethod
    def from_node(cls, node: Node) -> "ModuleCover":
        assert node.name == "module_cover", f"Expected module_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class LessonSubpartCover(FrameBase):
    image: dict
    intro: str
    title: str

    @classmethod
    def from_node(cls, node: Node) -> "LessonSubpartCover":
        assert node.name == "lesson_subpart_cover", f"Expected lesson_subpart_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)
    
    
class CaseStudyCover(FrameBase):
    image: dict
    intro: str
    title: str
    subtitle: str

    @classmethod
    def from_node(cls, node: Node) -> "LessonSubpartCover":
        assert node.name == "case_study_cover", f"Expected case_study_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class LessonPartCover(FrameBase):
    image: dict
    intro: str
    title: str

    @classmethod
    def from_node(cls, node: Node) -> "LessonPartCover":
        assert node.name == "lesson_part_cover", f"Expected lesson_part_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


class ChapterCover(FrameBase):
    image: dict
    chapter: Union[dict, str]
    title: str
    cta: Union[str, None] = Field(default="Scroll, tab or use your keyboard to move ahead")
    intro: str

    @classmethod
    def from_node(cls, node: Node) -> "ChapterCover":
        assert node.name == "chapter_cover", f"Expected chapter_cover node, got {node.name}"
        cover_data = parse_cover_fields(node)
        cover_data["image"] = dict(cover_data.get("image", {}))
        return cls(**cover_data)


# --- Connection Frames ---
class ConnectionNext(FrameBase):
    image: dict
    intro: str
    title: str
    nextLessonId: str
    cta: str = Field(default="Start learning")

    @classmethod
    def from_node(cls, node: Node) -> "ConnectionNext":
        assert node.name == "connection_next", f"Expected connection_next node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        return cls(
            template_id=node.name,
            image=dict(parse_image_fields(image_node)),
            intro=safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            cta=safe_get_characters(node, "cta", node.name),
            nextLessonId="1.1.1" ##this needs to be patched
        )


class ConnectionBack(FrameBase):
    image: dict
    intro: str
    title: str
    cta: Union[str, None] = None

    @classmethod
    def from_node(cls, node: Node) -> "ConnectionBack":
        assert node.name == "connection_back", f"Expected connection_back node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        return cls(
            template_id=node.name,
            image=dict(parse_image_fields(image_node)),
            intro=safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            cta=safe_get_characters(node, "cta", node.name)
        )


# --- Content Frames ---
class KeyConcepts(FrameBase):
    title: str
    intro: str
    concepts: List[Concept]

    @classmethod
    def from_node(cls, node: Node) -> "KeyConcepts":
        assert node.name == "key_concepts", f"Expected key_concepts node, got {node.name}"
        return cls(
            template_id=node.name,
            color_scheme="dark",
            intro=safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            concepts=[Concept.from_node(child) for child in node.select_nodes("GROUP", "concepts")],
        )


class LearningObjectives(FrameBase):
    title: str
    intro: str
    objectives: List[Card]

    @classmethod
    def from_node(cls, node: Node) -> "LearningObjectives":
        assert node.name == "learning_objectives", f"Expected learning_objectives node, got {node.name}"
        return cls(
            template_id=node.name,
            intro="",#safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            objectives=[Card.from_node(child) for child in node.select_nodes("GROUP", "objectives")],
        )


class KeyTakeaways(FrameBase):
    title: str
    intro: str
    takeaways: List[Card]

    @classmethod
    def from_node(cls, node: Node) -> "KeyTakeaways":
        assert node.name == "key_takeaways", f"Expected key_takeaways node, got {node.name}"
        return cls(
            template_id=node.name,
            intro="",#safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            takeaways=[Card.from_node(child) for child in node.select_nodes("GROUP", "objectives")],
        )
        


class ListOfLessons(FrameBase):
    title: str
    lessons: List[LessonThumbnail]

    @classmethod
    def from_node(cls, node: Node) -> "ListOfLessons":
        assert node.name == "list_of_lessons", f"Expected list_of_lessons node, got {node.name}"
        return cls(
            template_id=node.name,
            title=safe_get_characters(node, "title", node.name),
            lessons=[LessonThumbnail.from_node(child) for child in node.select_nodes("GROUP", "lessons")],
        )

# --- Embed Frame ---
class Embed(FrameBase):
    size: Literal["full", "half"]
    title: str
    url: str

    @classmethod
    def from_node(cls, node: Node) -> "Embed":
        assert node.name.strip().lower() == "embed", f"Expected embed node, got {node.name}"

        # Size logic (consistent with other visual blocks)
        width = node.absoluteBoundingBox["width"] if node.absoluteBoundingBox else 1000
        size: Literal["full", "half"] = "full" if width >= 1000 else "half"

        # Title: ONLY from TEXT node named "title"
        title = ""
        for child in node.children or []:
            if child.type == "TEXT" and child.name.strip().lower() == "title":
                title = (child.characters or "").strip()
                break

        # URL: name of the image element (RECTANGLE with IMAGE fill)
        url = ""
        for child in node.children or []:
            if child.type == "RECTANGLE":
                url = (child.name or "").strip()
                break

        if not url:
            raise ValueError("Embed frame missing URL: expected image element name to contain URL")

        return cls(
            template_id="embed",
            color_scheme="light",
            size=size,
            title=title,
            url=url,
        )



TEXT_TEMPLATE_IDS = [
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
    "subtitle_small"
]

class ModuleText(FrameBase):
    text_elements: List[dict]

    TEMPLATE_FIELDS: ClassVar[dict] = {
        "quote_large_with_name": ["quote", "author"],
        "quote_large_without_name": ["quote"],
        "quote_small_with_name": ["quote", "author"],
        "quote_small_without_name": ["quote"],
        "subtitle": ["text"],
        "subtitle_small": ["text"],
        "paragraph_large": ["text"],
        "paragraph_medium": ["text"],
        "paragraph_small": ["text"],
        "bullet_point": ["title", "body"],
        "bullet_point_with_highlight": ["title", "body", "source"],
        "bullet_point_with_number": ["number", "title", "body"],
        "kpi_highlight_large": ["value", "text"],
        "kpi_highlight_medium": ["value", "text"],
    }


    @classmethod
    def from_node(cls, node):
        assert node.name == "text", f"Expected text node, got {node.name}"

        raw_elements = [cls._parse_group(group) for group in getattr(node, "children", [])]
        elements = list(reversed([el for el in raw_elements if el]))

        # Assign local bullet numbers for each contiguous block
        bullet_count = 0
        for el in elements:
            if el["template_id"] == "bullet_point_with_number":
                bullet_count += 1
                el["content"]["number"] = str(bullet_count)
            else:
                bullet_count = 0  # reset counter when block breaks

        return cls(template_id="text", text_elements=elements)




    @classmethod
    def _parse_group(cls, group):
        template_id = group.name.lower()
        if template_id not in cls.TEMPLATE_FIELDS:
            return None

        expected_fields = cls.TEMPLATE_FIELDS[template_id]
        content = {field: "" for field in expected_fields}

        children = getattr(group, "children", [])
        field_idx = 0

        for child in children:
            if child.type != "TEXT":
                continue

            name = child.name.strip().lower() if child.name else ""
            if name in expected_fields:
                field = name
            elif field_idx < len(expected_fields):
                field = expected_fields[field_idx]
            else:
                continue  # too many children
            field_idx += 1

            content[field] = cls._extract_styled_text(child).strip()

        return {"template_id": template_id, "content": content}


    @staticmethod
    def _get_style_attrs(style: dict) -> dict:
        return {
            "bold": style.get("fontWeight", 0) >= 700 or "Bold" in style.get("fontStyle", ""),
            "italic": "italic" in style.get("fontStyle", "").lower(),
            "underline": style.get("textDecoration", "").lower() == "underline",
            "url": style.get("hyperlink", {}).get("url") if style.get("hyperlink") else None,
        }

    @classmethod
    def _wrap_text(cls, text: str, attrs: dict) -> str:
        if not text:
            return text

        wrappers = []
        if attrs.get("underline"):
            wrappers.append(("u", {}))
        if attrs.get("italic"):
            wrappers.append(("em", {}))
        if attrs.get("bold"):
            wrappers.append(("strong", {}))
        if attrs.get("url"):
            wrappers.append(("a", {"href": attrs["url"]}))

        for tag, attr in wrappers:
            attr_str = " ".join(f'{k}="{v}"' for k, v in attr.items()) if attr else ""
            open_tag = f"<{tag} {attr_str}>" if attr_str else f"<{tag}>"
            close_tag = f"</{tag}>"
            text = f"{open_tag}{text}{close_tag}"

        return text

    @classmethod
    def _extract_styled_text(cls, node):
        text = node.characters or ""
        overrides = getattr(node, "characterStyleOverrides", [])
        style_table = getattr(node, "styleOverrideTable", {})
        result = []
        current_chunk = ""
        current_attrs = None

        for i, char in enumerate(text):
            override_idx = overrides[i] if i < len(overrides) else 0
            style = style_table.get(str(override_idx), {}) if override_idx else getattr(node, "style", {})
            attrs = cls._get_style_attrs(style)

            if current_attrs is None:
                current_attrs = attrs
                current_chunk = char
            elif attrs == current_attrs:
                current_chunk += char
            else:
                result.append(cls._wrap_text(current_chunk, current_attrs))
                current_chunk = char
                current_attrs = attrs

        if current_chunk:
            result.append(cls._wrap_text(current_chunk, current_attrs))

        return "<br />".join("".join(result).splitlines())

    def to_content(self) -> dict:
        return {
            "template_id": self.id,
            "color_scheme": self.color_scheme,
            "content": {
                "text_elements": self.text_elements
            }
        }


# --- Photo Frames ---
class PhotoVertical(FrameBase):
    image: dict

    @classmethod
    def from_node(cls, node: Node) -> "PhotoVertical":
        assert node.name == "photo-vertical", f"Expected photo-vertical node, got {node.name}"
        
        image_node = node.select_node("ATTR", "imageUrl")

        # Use your existing safe_get_characters function
        caption = safe_get_characters(node, "caption", node.name)
        if caption.strip().lower() == "image caption":
            caption = ""

        if image_node:
            image = {"src": image_node.value, "caption": caption, "url": None}
        else:
            image_node = node.select_node("GROUP", "image")
            image = dict(parse_image_fields(node))
            image["caption"] = caption  # attach caption here too

        return cls(
            template_id="photo_vertical",#node.name,
            color_scheme="light",
            image=image
        )


class PhotoHorizontal(FrameBase):
    image: dict
    title: str | None = None
    description: str | None = None
    caption: str | None = None

    @classmethod
    def from_node(cls, node: Node) -> "PhotoHorizontal":
        assert node.name == "photo-horizontal", f"Expected photo-horizontal node, got {node.name}"

        # Extract optional text fields
        title = safe_get_characters(node, "title", node.name)
        description = safe_get_characters(node, "description", node.name)
        caption = safe_get_characters(node, "caption", node.name)
        if caption.strip().lower() == "image caption":
            caption = ""

        # Extract image from ATTR or fallback to image group
        image_node = node.select_node("ATTR", "imageUrl")
        if image_node:
            image = {"src": image_node.value, "caption": caption, "url": None}
        else:
            image_node = node.select_node("GROUP", "image")
            image = dict(parse_image_fields(image_node or node))
            image["caption"] = caption

        return cls(
            template_id=node.name,
            color_scheme="light",
            image=image,
            title=title if title else None,
            description=description if description else None,
            caption=caption if caption else None
        )

        # --- Infographic Frame ---
class Infographic(FrameBase):
    """
    Exports to:

    {
      "template_id": "infographic",
      "color_scheme": "light",
      "size": "full" | "half",
      "content": {
        "image": {"src": "...", "caption": "..."},
        "metadata": {"title": "...", "subtitle": "...", "description": "...", "footnote": "..."}
      }
    }
    """
    size: Literal["full", "half"]
    image: dict
    metadata: dict

    # Default placeholder text that should be suppressed
    _DEFAULT_SUMMARY = "Summary of the diagram. Otherwise, feel free to remove it."
    _DEFAULT_NOTE = "Note if necessary; otherwise, feel free to remove it."

    @classmethod
    def from_node(cls, node: Node) -> "Infographic":
        assert node.name.strip().lower() == "infographic", f"Expected infographic node, got {node.name}"

        # Size
        width = node.absoluteBoundingBox["width"] if node.absoluteBoundingBox else 1000
        size: Literal["full", "half"] = "full" if width >= 1000 else "half"

        # ---- Image: first top-level RECTANGLE with IMAGE fill ----
        image_rect = None
        for child in (node.children or []):
            if getattr(child, "type", "") != "RECTANGLE":
                continue
            fills = getattr(child, "fills", []) or []
            if any(isinstance(f, dict) and f.get("type") == "IMAGE" for f in fills):
                image_rect = child
                break

        image_src = getattr(image_rect, "id", None) if image_rect else None

        # ---- Metadata: pull from the "Light Template" INSTANCE ----
        template_inst = next(
            (c for c in (node.children or []) if getattr(c, "type", "") == "INSTANCE" and (c.name or "").strip().lower() == "light template"),
            None
        )

        def _text_by_name(inst: Node, text_name: str) -> tuple[str, Node | None]:
            """
            Returns (text, text_node). If missing -> ("", None)
            """
            if not inst:
                return ("", None)
            for c in (inst.children or []):
                if getattr(c, "type", "") == "TEXT" and (c.name or "").strip().lower() == text_name.lower():
                    # Preserve styled links/underline etc. when present
                    try:
                        return (ModuleText._extract_styled_text(c).strip(), c)
                    except Exception:
                        return ((getattr(c, "characters", "") or "").strip(), c)
            return ("", None)

        title, _ = _text_by_name(template_inst, "Title")
        subtitle, subtitle_node = _text_by_name(template_inst, "Summary")
        footnote, _ = _text_by_name(template_inst, "Source")
        description, _ = _text_by_name(template_inst, "Note")

        # Suppress default placeholder summary (even if the node is hidden)
        if subtitle.strip() == cls._DEFAULT_SUMMARY:
            subtitle = ""

        # Suppress default placeholder note (same idea)
        if description.strip() == cls._DEFAULT_NOTE:
            description = ""

        # (Optional) If Summary is hidden and you want it blank regardless, uncomment:
        # if subtitle_node is not None and getattr(subtitle_node, "visible", True) is False:
        #     subtitle = ""

        return cls(
            template_id="infographic",
            color_scheme="light",
            size=size,
            image={
                "src": image_src,
                "caption": ""
            },
            metadata={
                "title": title or "",
                "subtitle": subtitle or "",
                "description": description or "",
                "footnote": footnote or "",
            }
        )





# --- Chart Frame ---
# Chart metadata (title/subtitle/description/footnote) should come from the Charts Tracker workbook,
# loaded ONCE by the pipeline and injected via set_chart_metadata_map(...).

CHART_METADATA_MAP: dict = {}


def set_chart_metadata_map(metadata_map: dict) -> None:
    """Inject a pre-loaded {figure_id: {title,subtitle,description,footnote}} map."""
    global CHART_METADATA_MAP
    CHART_METADATA_MAP = metadata_map or {}


def load_chart_metadata_from_tracker_xlsx(xlsx_path: str) -> dict:
    """
    Loads chart metadata from Charts Tracker.xlsx.
    Returns: {Figure ID -> {title, subtitle, description, footnote}}
    Notes:
      - Subtitle is not present in the current tracker; defaults to "".
      - Description is mapped from 'Notes' when present; defaults to "".
      - Footnote is mapped from 'Footnote' when present; defaults to "".
    """

    xl = _pd.ExcelFile(xlsx_path)
    module_sheets = [s for s in xl.sheet_names if _re.fullmatch(r"Module\d+", str(s) or "")]

    def _load_module_sheet(sheet_name: str) -> _pd.DataFrame | None:
        raw = _pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
        header_row = None
        for i, row in raw.iterrows():
            if (row.astype(str).str.strip() == "Figure ID").any():
                header_row = i
                break
        if header_row is None:
            return None
        headers = raw.iloc[header_row].tolist()
        df = raw.iloc[header_row + 1 :].copy()
        df.columns = headers
        return df

    meta: dict = {}
    for sheet in module_sheets:
        df = _load_module_sheet(sheet)
        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            fig = str(row.get("Figure ID", "") or "").strip()
            if not fig or fig.lower() == "nan":
                continue

            title = str(row.get("Title", "") or "").strip()
            footnote = str(row.get("Footnote", "") or "").strip()
            notes = str(row.get("Notes", "") or "").strip()

            ##adjust this once the tracker matches
            meta[fig] = {
                "title": title,
                "subtitle": "",
                "description": notes,
                "footnote": footnote,
            }

    return meta


class Chart(FrameBase):
    size: Literal["full", "half"]
    metadata: dict
    option: dict

    @classmethod
    def from_node(cls, node: Node) -> "Chart":
        assert node.name == "chart", f"Expected chart node, got {node.name}"

        width = node.absoluteBoundingBox["width"] if node.absoluteBoundingBox else 1000
        size: Literal["full", "half"] = "full" if width >= 1000 else "half"

        # Use the chart image rectangle's *name* as the Figure ID (e.g., M1_C1_2)
        image_node = next((child for child in (node.children or []) if getattr(child, "type", "") == "RECTANGLE"), None)
        if not image_node:
            raise ValueError("Chart must contain a RECTANGLE node (used to hold the Figure ID)")

        chart_id = (getattr(image_node, "name", "") or "").strip()
        if not chart_id:
            raise ValueError("Chart RECTANGLE missing name (expected Figure ID, e.g., M1_C1_2)")

        chart_path = Path("../03_Outputs/charts/Auto Charts/DarkMode") / f"{chart_id}.json"
        if not chart_path.exists():
            raise ValueError(f"Chart JSON not found for: {chart_id}")

        with open(chart_path, "r", encoding="utf-8") as f:
            option = json.load(f)

        # Pull chart metadata from the pre-loaded tracker map.
        meta = CHART_METADATA_MAP.get(chart_id, {}) if isinstance(CHART_METADATA_MAP, dict) else {}
        metadata = {
            "title": str(meta.get("title", "") or ""),
            "subtitle": str(meta.get("subtitle", "") or ""),
            "description": str(meta.get("description", "") or ""),
            "footnote": str(meta.get("footnote", "") or ""),
        }

        return cls(
            template_id="echarts_chart",
            color_scheme="dark",
            size=size,
            metadata=metadata,
            option=option,
        )



# class Chart(FrameBase):
#     size: Literal["full", "half"]
#     option: dict

#     @classmethod
#     def from_node(cls, node: Node) -> "Chart":
#         assert node.name == "chart", f"Expected chart node, got {node.name}"

#         width = node.absoluteBoundingBox["width"] if node.absoluteBoundingBox else 1000
#         size = "full" if width >= 1000 else "half"

#         # --- Extract children ---
#         image_node = next((child for child in node.children if child.type == "RECTANGLE"), None)
#         group_node = next((child for child in node.children if child.name == "Light Template"), None)

#         if not image_node or not group_node:
#             raise ValueError("Chart must contain an image node and a 'Light Template' group")

#         # --- Extract Title, Summary, Source from Light Template group ---
#         text_map = {child.name: child.characters.strip() for child in group_node.children if child.type == "TEXT"}
#         title_text = text_map.get("Title", "")
#         summary_text = text_map.get("Summary", "")
#         source_text = text_map.get("Source", "")

#         # --- Load ECharts config by image name ---
#         chart_id = image_node.name
#         print(chart_id)
#         chart_path = Path("../03_Outputs/charts/Auto Charts/DarkMode") / f"{chart_id}.json" ##add handling of light/dark modes
#         if not chart_path.exists():
#             print(chart_id, "missing")

#             raise ValueError(f"Chart JSON not found for: {chart_id}")


#         with open(chart_path, "r", encoding="utf-8") as f:
#             option = json.load(f)

        
#         ###test content to insert style materials
#         # # --- Inject title and subtext ---
#         # option["title"] = {
#         #     "text": title_text,
#         #     "subtext": "",#source_text,
#         #     "left": "center",
#         #     "top": 20,
#         #     "textStyle": {
#         #         "color": "#ffffff",
#         #         "fontSize": 22,
#         #         "fontWeight": "bold",
#         #         "fontFamily": "Proxima Nova, sans-serif"
#         #     },
#         #     "subtextStyle": {
#         #         "color": "#666666",
#         #         "fontSize": 14,
#         #         "fontFamily": "Proxima Nova, sans-serif"
#         #     }
#         # }

#         # # --- Ensure grid spacing ---
#         # option["grid"] = option.get("grid", {})
#         # option["grid"].update({
#         #     "top": 200,
#         #     "bottom": 90,
#         #     "left": 70,
#         #     "right": 40
#         # })

#         # # --- Add summary as graphic block between subtext and chart ---
#         # option["graphic"] = {
#         #     "elements": [
#         #         {
#         #             "type": "text",
#         #             "left": "center",
#         #             "top": 80,
#         #             "style": {
#         #                 "text": "",#summary_text,
#         #                 "fill": "#444444",
#         #                 "font": "15px Proxima Nova, sans-serif",
#         #                 "width": 600,
#         #                 "lineHeight": 22,
#         #                 "align": "center"
#         #             }
#         #         }
#         #     ]
#         # }

#         return cls(
#             template_id="echarts_chart",
#             color_scheme="light",
#             size=size,
#             option=option
#         )


# --- Poll Frame ---
class Poll(FrameBase):
    pollId: str
    title: str
    description: str
    options: List[dict]
    labels: dict

    @classmethod
    def from_node(cls, node: Node) -> "Poll":
        assert node.name.strip().lower() == "poll", f"Expected poll node, got {node.name}"

        # Stable poll ID from figma node id
        poll_id = (
            f"poll-{node.id.replace(':', '-').replace('/', '-')}"
            if getattr(node, "id", None)
            else "poll"
        )

        # Title: GROUP "subtitle" -> TEXT "text"
        subtitle = node.select_node("GROUP", "subtitle")
        title = safe_get_characters(subtitle, "text", "poll") if subtitle else ""

        # Description / question: GROUP "paragraph_medium" -> TEXT "text"
        paragraph = node.select_node("GROUP", "paragraph_medium")
        description = safe_get_characters(paragraph, "text", "poll") if paragraph else ""

        # Options: repeated GROUP "answer_box"
        # Prefer TEXT "body", fallback to TEXT "title"
        values: List[str] = []
        for opt in node.select_nodes("GROUP", "answer_box") or []:
            v = safe_get_characters(opt, "body", "poll").strip()
            if not v:
                v = safe_get_characters(opt, "title", "poll").strip()
            if v:
                values.append(v)

        options = [{"id": i + 1, "value": v} for i, v in enumerate(values)]

        return cls(
            template_id="poll",
            color_scheme="light",
            pollId=poll_id,
            title=title,
            description=description,
            options=options,
            labels={
                "submit": "Submit",
                "cancel": "Cancel",
                "edit": "Edit your response",
                "votingAs": "Voting as",
            },
        )

class Video(FrameBase):

    size: Literal["full"] = "full"
    src: str
    poster: str

    @classmethod
    def from_node(cls, node: Node) -> "Video":
        assert node.name == "video", f"Expected video node, got {node.name}"

        # Find the first RECTANGLE with an IMAGE fill
        image_node = None
        for child in getattr(node, "children", []):
            if getattr(child, "type", "") == "RECTANGLE":
                fills = getattr(child, "fills", [])
                if isinstance(fills, list):
                    for fill in fills:
                        if isinstance(fill, dict) and fill.get("type") == "IMAGE":
                            image_node = child
                            break
                if image_node:
                    break

        if not image_node:
            raise ValueError("No valid image rectangle with IMAGE fill found in video")

        # Use the image node name as the video base filename
        video_name = image_node.name.strip()

        base_url = "https://sehseadata.blob.core.windows.net/images/Videos"
        src_url = f"{base_url}/src/{video_name}.mp4"
        poster_url = f"{base_url}/poster/{video_name}.png"

        return cls(
            template_id="video",
            color_scheme="light",
            size="full",
            src=src_url,
            poster=poster_url
        )

class PhotoFullHeight(FrameBase):
    image: dict

    @classmethod
    def from_node(cls, node: Node) -> "PhotoFullHeight":
        assert node.name == "photo-full-height", f"Expected photo-full-height node, got {node.name}"
        image_url = None

        # Iterate through node's children directly.
        if hasattr(node, "children"):
            for child in node.children:
                child_type = getattr(child, "type", "").upper()
                if child_type in ("ATTR", "RECTANGLE"):
                    image_url = getattr(child, "id", None)
                    if image_url:
                        break

        return cls(
            template_id="photo_full_height",#node.name,
            color_scheme="light",
            image={"src": image_url,"caption":""},
        )




# --- Outro Frames ---
class ChapterOutro(FrameBase):
    intro: str
    title: str
    subtitle: str
    body: str
    nextBlock: dict

    @classmethod
    def from_node(cls, node: Node) -> "ChapterOutro":
        assert node.name == "chapter_outro", f"Expected chapter_outro node, got {node.name}"
        nextBlock = NextBlock.from_node(node.select_node("GROUP", "quiz")).model_dump()
        nextBlock["nextBlockId"]= "1.1.5"
        titleNode=node.select_node("GROUP", "title")
        return cls(
            template_id=node.name,
            intro=safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(titleNode,"first_line", titleNode.name),
            subtitle=safe_get_characters(titleNode,"second_line", titleNode.name),
            body=safe_get_characters(node, "body", node.name),
            nextBlock=nextBlock
        )

class ModuleOutro(FrameBase):
    intro: str
    title: str
    subtitle: str
    body: str
    nextBlock: dict

    @classmethod
    def from_node(cls, node: Node) -> "ModuleOutro":
        assert node.name == "module_outro", f"Expected module_outro node, got {node.name}"
        title_node = node.select_node("GROUP", "title")
        first_line = safe_get_characters(title_node, "first_line", title_node.name).strip()

        # Infer module number from last character
        try:
            module_number = int(first_line[-1])
            next_module_id = f"{module_number + 1}.0.0"
        except (ValueError, IndexError):
            module_number = -1
            next_module_id = "1.0.0"  # Fallback if parsing fails

        next_block = NextBlock.from_node(node.select_node("GROUP", "quiz")).model_dump()
        next_block["nextBlockId"] = next_module_id

        return cls(
            template_id=node.name,
            intro=safe_get_characters(node, "intro", node.name),
            title=first_line,
            subtitle=safe_get_characters(title_node, "second_line", title_node.name),
            body=safe_get_characters(node, "body", node.name),
            nextBlock=next_block
        )


# --- Other Frames ---
class KeyResources(FrameBase):
    title: str
    intro: str
    resources: List[Card]

    @classmethod
    def from_node(cls, node: Node) -> "KeyResources":
        assert node.name == "key_resources", f"Expected key_resources node, got {node.name}"
        return cls(
            template_id=node.name,
            intro=safe_get_characters(node, "intro", node.name),
            title=safe_get_characters(node, "title", node.name),
            resources=[Card.from_node(child) for child in node.select_nodes("GROUP", "resources")]
        )



class ImageHotspot(FrameBase):
    image: dict
    hotspots: List[dict]

    @classmethod
    def from_node(cls, node: Node) -> "ImageHotspot":
        assert node.name == "image-hotspot", f"Expected image-hotspot node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        hotspots = [hotspot.to_dict() for hotspot in node.select_nodes("GROUP", "hotspot")]
        return cls(
            template_id=node.name,
            image=dict(parse_image_fields(image_node)),
            hotspots=hotspots
        )
        

