"""Adversarial Tester mode.

Triggered automatically on every increment tag push. Asks the LLM to invent
inputs that probe the assumptions visible in the student's diff, runs them
against the student's jar, and posts a Socratic summary of which inputs broke
what.

The mode degrades gracefully: if the project does not yet build (no
build.gradle, no jar), we post a one-paragraph note explaining what was
skipped. We never fail the workflow on the student's behalf.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .. import github, increments, issues, llm, repo

NUM_TEST_INPUTS = 12
RUN_TIMEOUT_SECONDS = 12
MAX_DIFF_CHARS = 10000

# Every scripted input ends with `bye` so a well-behaved chatbot will exit
# cleanly. We treat a missing terminating `bye` as a misconfiguration.
TERMINATOR = "bye"


def run(*, tag: str, sha: str) -> None:
    if not increments.get(tag):
        print(f"Tag {tag} is not in requirements.json; skipping")
        return

    prev = repo.previous_tag(tag)
    diff = repo.diff_between(prev, tag)
    requirements = increments.format_for_prompt(tag)

    if repo.is_javafx_project():
        summary = _gui_app_message(tag)
    else:
        jar = repo.build_jar()
        if jar is None:
            summary = _no_build_message(tag)
        else:
            scenarios = _generate_scenarios(tag, requirements, diff)
            results = _run_scenarios(jar, scenarios)
            summary = _summarise(tag, requirements, results)

    body = issues.adversarial_body(
        tag=tag,
        previous_tag=prev,
        sha=sha,
        requirements_url=increments.url_for(tag),
        summary=summary,
    )

    repo_name = github.repo()
    title = issues.title_for(tag)
    existing = github.find_issue_by_title(repo_name, title)
    if existing:
        github.update_issue(repo_name, existing["number"], body)
        print(f"Updated review issue #{existing['number']} for {tag}")
    else:
        created = github.create_issue(repo_name, title, body)
        print(f"Created review issue #{created['number']} for {tag}")


# --- LLM-driven input generation -------------------------------------------------

_SCENARIO_SYSTEM = (
    "You are a software tester for a beginner Java chatbot project (the CS2103T "
    "iP, a Duke-style command-line task manager). Your job is to invent CLI inputs "
    "that probe assumptions the student likely made in their parser or command "
    "handlers. You only generate inputs — you never write code, never explain "
    "fixes, and never grade.\n\n"
    "Reply with a single JSON object of the form:\n"
    '  {"scenarios": [ {"name": "...", "intent": "...", "lines": ["...", "..."]}, ... ]}\n'
    "where each `lines` array is the lines that will be piped to the chatbot's "
    "stdin in order. The chatbot expects one command per line. Do NOT include "
    "a final `bye` — the runner appends it.\n"
    "Generate inputs that target malformed syntax, missing arguments, ordering "
    "ambiguities, whitespace and empty inputs, very long inputs, out-of-range "
    "indices, and unicode where relevant. Avoid trivially valid inputs — those "
    "are not interesting."
)


def _generate_scenarios(tag: str, requirements: str, diff: str) -> list[dict]:
    user = (
        f"Increment tag: {tag}\n\n"
        f"Increment requirements:\n{requirements}\n\n"
        f"Diff since previous tag (may be empty if this is the first increment):\n"
        f"```diff\n{llm.truncate(diff, MAX_DIFF_CHARS)}\n```\n\n"
        f"Generate exactly {NUM_TEST_INPUTS} adversarial test scenarios as a JSON array."
    )
    try:
        payload = llm.chat_json(
            [
                {"role": "system", "content": _SCENARIO_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
    except Exception as exc:
        print(f"Scenario generation failed: {exc}")
        return []

    if isinstance(payload, dict):
        scenarios = payload.get("scenarios", [])
    elif isinstance(payload, list):
        # Legacy / fallback shape — accept it.
        scenarios = payload
    else:
        scenarios = []

    cleaned: list[dict] = []
    for s in scenarios if isinstance(scenarios, list) else []:
        lines = s.get("lines") or []
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            continue
        cleaned.append(
            {
                "name": str(s.get("name", "scenario"))[:80],
                "intent": str(s.get("intent", ""))[:200],
                "lines": lines[:20],
            }
        )
    return cleaned[:NUM_TEST_INPUTS]


# --- Execution ------------------------------------------------------------------


def _run_scenarios(jar: Path, scenarios: list[dict]) -> list[dict]:
    results: list[dict] = []
    for s in scenarios:
        stdin_text = "\n".join(s["lines"] + [TERMINATOR]) + "\n"
        stdout, stderr, exit_code = repo.run_jar(
            jar, stdin_text, timeout_seconds=RUN_TIMEOUT_SECONDS
        )
        results.append(
            {
                "name": s["name"],
                "intent": s["intent"],
                "stdin": stdin_text,
                "stdout": stdout[-2000:],
                "stderr": stderr[-1500:],
                "exit_code": exit_code,
                "verdict": _classify(stdout, stderr, exit_code),
            }
        )
    return results


def _classify(stdout: str, stderr: str, exit_code: int) -> str:
    if exit_code == -1:
        return "timeout"
    if exit_code != 0:
        return "nonzero_exit"
    lower_err = stderr.lower()
    if "exception" in lower_err or "error" in lower_err or "traceback" in lower_err:
        return "stderr_error"
    if "exception" in stdout.lower():
        return "stdout_exception"
    return "ok"


# --- Socratic summary -----------------------------------------------------------

_SUMMARY_SYSTEM = (
    "You are a tutor for the CS2103T iP. You are looking at the results of "
    "automated adversarial test inputs run against a student's chatbot. For "
    "each non-OK result, write ONE short Socratic observation that points at "
    "the assumption that broke. Do not provide corrected code. Do not name "
    "specific lines or methods unless they appear in the test output. Do not "
    "scold. Frame each observation as a question the student can think through.\n\n"
    "Your output must be valid GitHub-flavored markdown. Use this layout:\n\n"
    "**Summary:** <one short sentence with pass/fail counts>\n\n"
    "**Findings:**\n"
    "- ❌ `<input or scenario name>` — <one-sentence observation phrased as a question>\n"
    "- ✅ `<input or scenario name>` — handled as expected.\n\n"
    "List failures first. Cap the total at 8 bullets even if more results exist. "
    "If everything passed, say so plainly and offer one thing the student could "
    "stress-test next."
)


def _summarise(tag: str, requirements: str, results: list[dict]) -> str:
    if not results:
        return (
            "No adversarial test scenarios were generated for this push. "
            "The model did not return usable inputs — please re-run the workflow "
            "if you want to retry."
        )

    rendered = "\n\n".join(_render_for_prompt(r) for r in results)
    user = (
        f"Increment: {tag}\n\n"
        f"Increment requirements (for context):\n{requirements}\n\n"
        f"Test results (one block per scenario):\n\n{rendered}"
    )
    return llm.chat(
        [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": user},
        ]
    )


def _render_for_prompt(result: dict) -> str:
    parts = [
        f"### {result['name']}  [{result['verdict']}]",
        f"Intent: {result['intent']}",
        f"Stdin:\n```\n{result['stdin'].rstrip()}\n```",
        f"Exit code: {result['exit_code']}",
    ]
    if result["stdout"].strip():
        parts.append(f"Stdout:\n```\n{result['stdout'].strip()[:600]}\n```")
    if result["stderr"].strip():
        parts.append(f"Stderr:\n```\n{result['stderr'].strip()[:400]}\n```")
    return "\n".join(parts)


def _no_build_message(tag: str) -> str:
    return (
        f"The project at `{tag}` did not build into a runnable jar, so the "
        "adversarial tester could not execute any inputs. This is expected for "
        "early increments before `A-Gradle` and `A-Jar` are tagged. The reviewer "
        "will start running adversarial inputs once `./gradlew shadowJar` (or "
        "`./gradlew jar`) produces a jar in `build/libs/`."
    )


def _gui_app_message(tag: str) -> str:
    return (
        f"The project at `{tag}` looks like a JavaFX (GUI) app — "
        "`build.gradle` references the JavaFX plugin. The adversarial tester "
        "only applies while the chatbot is stdin-driven, so it has been "
        "skipped for this push.\n\n"
        "The Rubric Mapper (`/rubric`) and Code Quality (`/quality`) modes "
        "still apply at this stage and may be more useful here."
    )


def _expected_terminator() -> Optional[str]:
    return TERMINATOR
