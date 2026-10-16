from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


@dataclass(frozen=True)
class EnvConfig:
    figma_token: str | None = field(default=None, repr=False)
    figma_document_id1: str | None = None
    figma_document_id2: str | None = None
    figma_document_id3: str | None = None
    azure_openai_api_key: str | None = field(default=None, repr=False)
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str | None = None
    sas_url: str | None = field(default=None, repr=False)
    heygen_api_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(
        cls, load_dotenv_file: bool = True, dotenv_path: str | Path | None = None,
    ) -> "EnvConfig":
        if load_dotenv_file:
            load_dotenv(dotenv_path or Path(__file__).resolve().parents[2] / ".env", override=False)
        return cls(
            figma_token=os.getenv("FIGMA_TOKEN"),
            figma_document_id1=os.getenv("FIGMA_DOCUMENT_ID1"),
            figma_document_id2=os.getenv("FIGMA_DOCUMENT_ID2"),
            figma_document_id3=os.getenv("FIGMA_DOCUMENT_ID3"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            sas_url=os.getenv("SAS_URL"),
            heygen_api_key=os.getenv("HEYGEN_API_KEY"),
        )

    def validate_keys(self, keys: Iterable[str]) -> dict[str, object]:
        missing = []
        values: dict[str, object] = {}
        for key in keys:
            env_key = key.upper()
            value = os.getenv(env_key)
            # Validation results are displayed and saved in driver notebooks.
            values[env_key] = "[REDACTED]" if value else None
            if not value:
                missing.append(env_key)
        return {"ok": not missing, "missing": missing, "values": values}
