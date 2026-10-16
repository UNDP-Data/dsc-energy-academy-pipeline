from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .env import EnvConfig
from .paths import RepoPaths


DEFAULT_LANGUAGES = ("fr", "es", "pt", "ar", "zh", "ru")


@dataclass
class PipelineConfig:
    root_dir: Path
    paths: RepoPaths
    env: EnvConfig
    target_languages: tuple[str, ...] = DEFAULT_LANGUAGES
    notebook_timeout_seconds: int = 7200
    stage_options: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_repo_root(
        cls,
        root_dir: str | Path | None = None,
        load_dotenv_file: bool = True,
    ) -> "PipelineConfig":
        if root_dir is None:
            root_dir = Path(__file__).resolve().parents[3]
        paths = RepoPaths.from_root(root_dir)
        env = EnvConfig.from_environment(
            load_dotenv_file=load_dotenv_file, dotenv_path=paths.code_dir / ".env",
        )
        return cls(root_dir=paths.root_dir, paths=paths, env=env)
