"""Loader for the requirements.json increment specs."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DEFAULT_PATH_ENV = "IP_REVIEWER_REQUIREMENTS"


def _candidate_paths() -> list[Path]:
    override = os.environ.get(DEFAULT_PATH_ENV)
    if override:
        return [Path(override)]

    here = Path(__file__).resolve()
    return [
        Path(".github/ip-reviewer/requirements.json"),
        Path(".github/requirements.json"),
        here.parent.parent.parent / "data" / "requirements.json",
    ]


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    for path in _candidate_paths():
        if path.exists():
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            return data.get("increments", {})
    return {}


def get(tag: str) -> Optional[dict]:
    return load().get(tag)


def format_for_prompt(tag: str) -> str:
    entry = get(tag)
    if not entry:
        return f"(No requirements found for tag '{tag}'.)"

    lines = [f"## {entry.get('title', tag)} (Week {entry.get('week', '?')})", ""]
    if entry.get("description"):
        lines.append(entry["description"])
        lines.append("")

    if entry.get("requirements"):
        lines.append("**Must implement:**")
        for r in entry["requirements"]:
            lines.append(f"- {r}")
        lines.append("")

    if entry.get("constraints"):
        lines.append("**Constraints:**")
        for c in entry["constraints"]:
            lines.append(f"- {c}")
        lines.append("")

    return "\n".join(lines).rstrip()


def url_for(tag: str) -> Optional[str]:
    entry = get(tag)
    return entry.get("url") if entry else None
