"""Code Quality mode.

Triggered on-demand when a student comments `/quality` on a review issue.
Reads every Java source file under `src/main/`, then asks the LLM to:

1. Flag style violations against the embedded CS2103T coding standard, with
   `file:line` references.
2. Flag cross-file OOP smells that are only visible when several files are
   considered together (responsibility leaks, tight coupling).

The mode does not produce or suggest fixed code. Findings are framed as
specific references plus a question.
"""

from __future__ import annotations

from pathlib import Path

from .. import github, issues, llm, repo

MAX_FILE_CHARS = 6000
MAX_TOTAL_CHARS = 30000

_STANDARD_PATH_CANDIDATES = [
    Path(".github/ip-reviewer/coding-standard.md"),
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "coding-standard.md",
]


def run(*, tag: str, issue: dict) -> None:
    files = repo.java_source_files()
    if not files:
        body = issues.comment_body(
            "Code quality review",
            "No Java sources found under `src/`. Nothing to check.",
        )
        github.post_comment(github.repo(), issue["number"], body)
        return

    standard = _load_standard()
    rendered = _render_files(files)
    findings = _ask_llm(tag, standard, rendered)

    body = issues.comment_body("Code quality review", findings)
    github.post_comment(github.repo(), issue["number"], body)
    print(f"Posted quality review for {tag}")


def _load_standard() -> str:
    for path in _STANDARD_PATH_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return "(coding-standard.md not found — using defaults baked into the prompt)"


def _render_files(files: list[Path]) -> str:
    """Render each file with line numbers so the model can cite `file:line`."""
    parts: list[str] = []
    used = 0

    for path in files:
        contents = repo.read_file(path, max_chars=MAX_FILE_CHARS)
        if not contents:
            continue
        numbered = "\n".join(
            f"{i + 1:4d}  {line}" for i, line in enumerate(contents.splitlines())
        )
        chunk = f"===== {path} =====\n{numbered}\n"
        if used + len(chunk) > MAX_TOTAL_CHARS:
            parts.append("===== [remaining files omitted for prompt budget] =====\n")
            break
        parts.append(chunk)
        used += len(chunk)

    return "\n".join(parts)


_SYSTEM = (
    "You are a code-quality reviewer for the CS2103T iP. You will be given the "
    "CS2103T coding standard and the student's Java source files (with line "
    "numbers). Produce a focused, specific review.\n\n"
    "Rules:\n"
    "- Cite each finding as `path/to/File.java:LINE` (single line) or "
    "  `path/to/File.java:LINE-LINE` (range). Lines must come from the input.\n"
    "- Group findings under three headings: 'Style', 'Method/class structure', "
    "  'OOP and responsibility'. Skip a heading if you have nothing concrete.\n"
    "- For each finding write: the citation, one sentence describing what you "
    "  see, and one short Socratic question pointing at the assumption to "
    "  reconsider. Do NOT propose code.\n"
    "- Be specific. 'Method too long' alone is useless; 'Duke.java:42-118 — "
    "  `run()` mixes parsing, dispatch, and rendering. Which sub-responsibility "
    "  could move out first?' is useful.\n"
    "- Cap the report at roughly 12 findings. Prefer the most load-bearing.\n"
    "- If you find nothing notable, say so — do not invent issues."
)


def _ask_llm(tag: str, standard: str, rendered_sources: str) -> str:
    user = (
        f"Tag at time of review: {tag}\n\n"
        f"CS2103T coding standard (cite specific rules where they apply):\n\n"
        f"{standard}\n\n"
        f"Student's Java sources (with line numbers):\n\n{rendered_sources}"
    )
    return llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ]
    )
