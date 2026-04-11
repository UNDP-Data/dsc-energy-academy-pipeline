from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoPaths:
    root_dir: Path
    code_dir: Path
    api_dir: Path
    inputs_dir: Path
    outputs_dir: Path
    docs_dir: Path

    @classmethod
    def from_root(cls, root_dir: str | Path) -> "RepoPaths":
        root = Path(root_dir).resolve()
        return cls(
            root_dir=root,
            code_dir=root / "01_Code",
            api_dir=root / "00_API",
            inputs_dir=root / "02_Inputs",
            outputs_dir=root / "03_Outputs",
            docs_dir=root / "05_Documentation",
        )

    def resolve(self, *parts: str) -> Path:
        return self.root_dir.joinpath(*parts).resolve()
