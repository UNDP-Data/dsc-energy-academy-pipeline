from __future__ import annotations

import subprocess
import time
from pathlib import Path

from sea_pipeline.shared.config import PipelineConfig
from sea_pipeline.shared.redaction import SecretRedactor


AVATAR_SCRIPT_COMMANDS: dict[str, tuple[str, ...]] = {
    "generate_payloads": ("python3", "generate_payloads_avatars.py"),
    "generate_videos": ("python3", "generate_avatars_heygen.py"),
    "list_blob_clips": ("python3", "list_avatar_clips_in_azure_blob.py"),
    "download_blob_clips": ("python3", "download_avatar_clips_from_azure_blob.py"),
    "add_backgrounds": ("python3", "add_background_avatars.py"),
}


def run_avatar_script_command(config: PipelineConfig, command_name: str) -> dict[str, object]:
    if command_name not in AVATAR_SCRIPT_COMMANDS:
        raise KeyError(f"Unknown avatar script command: {command_name}")

    started = time.time()
    avatars_dir = config.paths.code_dir / "avatars"
    completed = subprocess.run(
        AVATAR_SCRIPT_COMMANDS[command_name],
        cwd=avatars_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    redactor = SecretRedactor((config.env.heygen_api_key, config.env.sas_url))
    return {
        "stage": command_name,
        "kind": "subprocess",
        "status": "ok" if completed.returncode == 0 else "error",
        "stdout": redactor.text(completed.stdout),
        "stderr": redactor.text(completed.stderr),
        "returncode": completed.returncode,
        "duration_seconds": time.time() - started,
        "workdir": str(Path(avatars_dir).resolve()),
    }
