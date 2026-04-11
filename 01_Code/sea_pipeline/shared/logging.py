from __future__ import annotations

from typing import Any


def format_stage_result(result: dict[str, Any]) -> str:
    lines = [
        f"Stage: {result.get('stage')}",
        f"Status: {result.get('status')}",
    ]
    if result.get("kind"):
        lines.append(f"Kind: {result['kind']}")
    if result.get("duration_seconds") is not None:
        lines.append(f"Duration: {result['duration_seconds']:.2f}s")
    if result.get("notebook"):
        lines.append(f"Notebook: {result['notebook']}")
    if result.get("stdout") and not result.get("stdout_streamed"):
        lines.append("Stdout:")
        lines.extend(str(result["stdout"]).splitlines())
    if result.get("stderr") and not result.get("stderr_streamed"):
        lines.append("Stderr:")
        lines.extend(str(result["stderr"]).splitlines())
    if result.get("summary"):
        lines.append(f"Summary: {result['summary']}")
    return "\n".join(lines)


def print_stage_result(result: dict[str, Any]) -> None:
    print(format_stage_result(result))
