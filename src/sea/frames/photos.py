"""
Photo-related frames.
"""

from ..entities.components import Image
from ..entities.node import Node
from .base import FrameBase


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
