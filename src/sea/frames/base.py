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
        content = self.model_dump(exclude=fields, by_alias=True)
        return self.model_dump(include=fields, by_alias=True) | {"content": content}


class FrameBase(BaseModel):
    """
    Base class for all frames.
    This version builds the final output dictionary manually (preserving field order)
    by iterating over the fields in the order they were declared.
    """

    id: str = Field(alias="template_id")
    colorscheme: Literal["light", "dark"] | None = Field(default=None)

    def to_content(self) -> dict:
        meta = {"template_id": self.id, "colorscheme": self.colorscheme}
        content = {}
        # Iterate over the fields in the order of declaration.
        for field in self.__fields__:
            if field in {"template_id", "colorscheme", "id"}:
                continue
            value = getattr(self, field)
            content[field] = self._serialize_value(value)
        meta["content"] = content
        return meta

    def _serialize_value(self, value):
        if isinstance(value, BaseModel):
            # Recursively dump nested Pydantic models.
            return (
                value.to_content()
                if hasattr(value, "to_content")
                else value.model_dump()
            )
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            new_dict = {}
            for k, v in value.items():
                new_dict[k] = self._serialize_value(v)
            return new_dict
        else:
            return value
