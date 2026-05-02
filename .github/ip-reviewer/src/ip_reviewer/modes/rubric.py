"""Rubric Mapper mode.

Triggered on-demand when a student comments `/rubric` on a review issue.
Walks the repo, builds a compact file inventory + per-file digest, then asks
the LLM to map each rubric criterion to evidence in the student's code and
flag any gaps.

The mapper is *not* a grader. It produces a checklist a student can act on
before submission, not a score.
"""

from __future__ import annotations

from pathlib import Path

from .. import github, increments, issues, llm, repo

MAX_FILE_HEAD_CHARS = 1500
MAX_TOTAL_DIGEST_CHARS = 18000

_RUBRIC_PATH_CANDIDATES = [
    Path(".github/ip-reviewer/rubric.md"),
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "rubric.md",
]


def run(*, tag: str, issue: dict) -> None:
    rubric_text = _load_rubric()
    inventory = _build_inventory()
    increment_summary = increments.format_for_prompt(tag)

    if not inventory:
        body = issues.comment_body(
            "Rubric mapping",
            "I could not find any Java sources under `src/`. Re-run after the "
            "repo has source files in place.",
        )
        github.post_comment(github.repo(), issue["number"], body)
        return

    mapping = _ask_llm(tag, rubric_text, increment_summary, inventory)
    body = issues.comment_body("Rubric mapping", mapping)
    github.post_comment(github.repo(), issue["number"], body)
    print(f"Posted rubric mapping for {tag}")


def _load_rubric() -> str:
    for path in _RUBRIC_PATH_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return "(rubric.md not found — using defaults baked into the prompt)"


def _build_inventory() -> str:
    files = repo.java_source_files()
    if not files:
        return ""

    parts: list[str] = []
    used = 0
    for path in files:
        head = repo.read_file(path, max_chars=MAX_FILE_HEAD_CHARS)
        chunk = f"--- {path} ---\n{head.rstrip()}\n"
        if used + len(chunk) > MAX_TOTAL_DIGEST_CHARS:
            parts.append("... [remaining files truncated for prompt budget]\n")
            break
        parts.append(chunk)
        used += len(chunk)

    return "\n".join(parts)


_SYSTEM = (
    "You are mapping a CS2103T iP submission to its assessment criteria. You "
    "are NOT grading. You produce a structured markdown report that, for each "
    "criterion, identifies (a) which files/classes/methods evidence the "
    "criterion and (b) what is still missing.\n\n"
    "Rules:\n"
    "- Cite specific files (and line ranges if you can infer them) using "
    "  backticks.\n"
    "- Do not invent files that aren't in the inventory.\n"
    "- Do not write code or suggest line-level fixes.\n"
    "- Frame gaps as concrete next actions the student can take.\n"
    "- Be concise. Aim for 2-4 sentences per criterion.\n\n"
    "Output structure:\n"
    "## Summary\n"
    "<one paragraph: where the submission stands overall against the rubric>\n\n"
    "## Criterion: <name>\n"
    "**Evidence:** <files / what they demonstrate>\n"
    "**Gaps:** <what is missing, or 'none observed'>\n"
    "(repeat for each criterion in the rubric)\n"
)


def _ask_llm(tag: str, rubric_text: str, increment_summary: str, inventory: str) -> str:
    user = (
        f"Most recent tag: {tag}\n\n"
        f"Increment context:\n{increment_summary}\n\n"
        f"Rubric:\n{rubric_text}\n\n"
        f"Repo inventory (Java sources, file head shown):\n\n{inventory}"
    )
    return llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ]
    )
