"""Reject unsafe files and notebook outputs in the Git index without printing secrets."""
from __future__ import annotations

import json
import subprocess
from pathlib import PurePosixPath


def check_path(name: str, content: bytes | None = None) -> list[str]:
    path = PurePosixPath(name)
    errors = []
    if (path.name == ".env" or path.name.startswith(".env.")) and path.name not in {".env.example", ".env.template"}:
        errors.append("private environment file")
    if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        errors.append("private key/certificate file")
    if (path.name == ".DS_Store" or path.suffix in {".pyc", ".pyo"}
            or any(part in {"__pycache__", ".ipynb_checkpoints", ".venv", "venv", ".aws", ".azure"} for part in path.parts)):
        errors.append("local/generated artifact")
    notebook = path.suffix == ".ipynb" or ("_legacy_notebooks" in path.parts and path.suffix == ".json")
    if notebook and content is not None:
        try:
            data = json.loads(content)
            if any(cell.get("outputs") or cell.get("execution_count") is not None for cell in data.get("cells", [])):
                errors.append("saved notebook execution output; clear before staging")
            if data.get("metadata", {}).get("widgets"):
                errors.append("saved notebook widget state")
        except (ValueError, AttributeError):
            errors.append("invalid notebook JSON")
    return errors


def main() -> int:
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    failures = []
    for name in filter(None, names):
        path = PurePosixPath(name)
        is_notebook = path.suffix == ".ipynb" or ("_legacy_notebooks" in path.parts and path.suffix == ".json")
        content = subprocess.check_output(["git", "show", f":{name}"]) if is_notebook else None
        failures.extend(f"{name}: {error}" for error in check_path(name, content))
    for failure in failures:
        print(failure)
    print(f"Repository hygiene: {len(failures)} issue(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
