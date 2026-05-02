"""Issue body construction and metadata.

The reviewer keeps a small JSON blob inside an HTML comment in each issue body
so we can recover what the issue is about without re-deriving from the title.
This is the only state the system carries between runs.
"""

from __future__ import annotations

import json
import re
from typing import Optional

TITLE_PREFIX = "iP Review:"
META_OPEN = "<!-- ip-reviewer:"
META_CLOSE = " -->"
DISCLAIMER = (
    "_Automated review. May not be 100% accurate — use your own judgement and "
    "ask your TA if unsure._"
)
COMMENT_HINT = (
    "Reply with `/rubric` to map your repo against the assessment criteria, or "
    "`/quality` to check it against the CS2103T coding standard."
)


def title_for(tag: str) -> str:
    return f"{TITLE_PREFIX} {tag}"


def encode_metadata(metadata: dict) -> str:
    return f"{META_OPEN}{json.dumps(metadata, separators=(',', ':'))}{META_CLOSE}"


def parse_metadata(body: Optional[str]) -> dict:
    if not body:
        return {}
    match = re.search(r"<!-- ip-reviewer:(.*?) -->", body, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def is_review_issue(issue: dict) -> bool:
    title = issue.get("title", "")
    body = issue.get("body", "") or ""
    return title.startswith(TITLE_PREFIX) and META_OPEN in body


def tag_from_issue(issue: dict) -> Optional[str]:
    meta = parse_metadata(issue.get("body", ""))
    if meta.get("tag"):
        return meta["tag"]
    title = issue.get("title", "") or ""
    if title.startswith(TITLE_PREFIX):
        return title[len(TITLE_PREFIX):].strip()
    return None


def adversarial_body(
    *,
    tag: str,
    previous_tag: Optional[str],
    sha: str,
    requirements_url: Optional[str],
    summary: str,
) -> str:
    lines = [
        f"## {title_for(tag)}",
        "",
        f"- Tag: `{tag}`",
        f"- Commit: `{sha}`",
    ]
    if previous_tag:
        lines.append(f"- Previous tag: `{previous_tag}`")
    if requirements_url:
        lines.append(f"- Requirements: [{tag}]({requirements_url})")
    lines.extend(
        [
            "",
            "### Adversarial test results",
            "",
            summary.strip(),
            "",
            COMMENT_HINT,
            "",
            DISCLAIMER,
            "",
            encode_metadata({"tag": tag, "sha": sha, "previous_tag": previous_tag, "kind": "adversarial"}),
        ]
    )
    return "\n".join(lines)


def comment_body(heading: str, content: str) -> str:
    return f"### {heading}\n\n{content.strip()}\n\n{DISCLAIMER}"
