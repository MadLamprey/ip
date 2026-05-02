"""Entry point dispatcher.

Two GitHub Actions events route here:

- `push` (tag) → run the adversarial tester and create/update the review issue.
- `issue_comment` → if the comment is a slash command on a review issue, route
  to the matching mode.
"""

from __future__ import annotations

import sys
import traceback

from . import github, issues
from .modes import adversarial, quality, rubric

SLASH_COMMANDS = {
    "/rubric": rubric.run,
    "/quality": quality.run,
}


def _run_tag_push() -> int:
    import os

    ref = os.environ.get("GITHUB_REF", "")
    if not ref.startswith("refs/tags/"):
        print(f"Push event ref is not a tag: {ref!r}")
        return 0

    tag = ref[len("refs/tags/"):]
    sha = os.environ.get("GITHUB_SHA", "")
    adversarial.run(tag=tag, sha=sha)
    return 0


def _run_issue_comment() -> int:
    payload = github.event_payload()
    if payload.get("action") != "created":
        print(f"Ignoring issue_comment action: {payload.get('action')}")
        return 0

    issue = payload.get("issue", {}) or {}
    comment = payload.get("comment", {}) or {}

    if (comment.get("user") or {}).get("type") == "Bot":
        print("Ignoring bot-authored comment")
        return 0

    if not issues.is_review_issue(issue):
        print("Comment is on a non-review issue; ignoring")
        return 0

    body = (comment.get("body") or "").strip()
    command = body.split()[0] if body else ""
    handler = SLASH_COMMANDS.get(command)
    if not handler:
        print(f"No matching slash command for {command!r}; ignoring")
        return 0

    tag = issues.tag_from_issue(issue)
    if not tag:
        print("Could not determine tag for issue")
        return 1

    handler(tag=tag, issue=issue)
    return 0


def main() -> int:
    import os

    event = os.environ.get("GITHUB_EVENT_NAME", "")
    try:
        if event == "push":
            return _run_tag_push()
        if event == "issue_comment":
            return _run_issue_comment()
        print(f"Unsupported event: {event!r}")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
