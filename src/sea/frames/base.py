"""
Base frame class definition.
"""

from typing import Literal

from pydantic import BaseModel, Field

__all__ = ["FrameBase"]


class FrameBase(BaseModel):
    """
    Base class all frames inherit from.
    """

    id: str = Field(alias="template_id")
    colorscheme: Literal["light", "dark"] | None = Field(default=None)

    def to_content(self) -> dict:
        """
        Dumpt the model to a dictionary with content.

        Returns
        -------
        dict
            The model dictionary with non-metadata fields wrapped in "content".
        """
        fields = {"id", "colorscheme"}
        content = self.model_dump(exclude=fields)
        return self.model_dump(include=fields) | {"content": content}
