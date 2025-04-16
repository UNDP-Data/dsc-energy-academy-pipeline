"""
Photo-related frames.
"""

from ..nodes import Node
from .base import FrameBase
from .utils import Image, parse_image_fields


class PhotoVertical(FrameBase):
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


# --- Photo Frames ---
class PhotoVertical(FrameBase):
    image: dict

    @classmethod
    def from_node(cls, node: Node) -> "PhotoVertical":
        assert (
            node.name == "photo-vertical"
        ), f"Expected photo-vertical node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        return cls(
            template_id=node.name,
            colorscheme="light",
            image=dict(parse_image_fields(image_node)),
        )


class PhotoHorizontal(FrameBase):
    image: dict

    @classmethod
    def from_node(cls, node: Node) -> "PhotoHorizontal":
        # For photo-horizontal, extract image directly using the "imageUrl" attribute.
        assert (
            node.name == "photo-horizontal"
        ), f"Expected photo-horizontal node, got {node.name}"
        image_url_node = node.select_node("ATTR", "imageUrl")
        image_url = image_url_node.value if image_url_node else None
        return cls(
            template_id=node.name,
            colorscheme="light",
            image={"src": image_url, "caption": None, "url": None},
        )


class PhotoFullHeight(FrameBase):
    image: dict

    @classmethod
    def from_node(cls, node: Node) -> "PhotoFullHeight":
        assert (
            node.name == "photo-full-height"
        ), f"Expected photo-full-height node, got {node.name}"
        image_url = None

        # Iterate through node's children directly.
        if hasattr(node, "children"):
            for child in node.children:
                child_type = getattr(child, "type", "").upper()
                if child_type in ("ATTR", "RECTANGLE"):
                    image_url = getattr(child, "name", None)
                    if image_url:
                        break

        return cls(
            template_id=node.name,
            colorscheme="light",
            image={"src": image_url, "caption": ""},
        )


class ImageHotspot(FrameBase):
    image: Image
    hotspots: list[dict]

    @classmethod
    def from_node(cls, node: Node) -> "ImageHotspot":
        assert (
            node.name == "image-hotspot"
        ), f"Expected image-hotspot node, got {node.name}"
        image_node = node.select_node("GROUP", "image")
        hotspots = [
            hotspot.to_dict() for hotspot in node.select_nodes("GROUP", "hotspot")
        ]
        return cls(
            template_id=node.name,
            image=Image.from_node(image_node),
            hotspots=hotspots,
        )
