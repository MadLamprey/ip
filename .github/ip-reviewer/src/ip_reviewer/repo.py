"""Repo-side helpers: git, file scanning, jar build/run.

Everything that touches the student's working tree lives here so the mode
modules can stay focused on their LLM prompts.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional

INCREMENT_PREFIXES = ("Level-", "A-", "B-")


def _git(*args: str, cwd: Optional[str] = None) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return result.stdout


def all_increment_tags() -> list[str]:
    """All tags matching the increment prefixes, oldest first."""
    out = _git("for-each-ref", "--sort=creatordate", "--format=%(refname:short)", "refs/tags")
    tags = [t.strip() for t in out.splitlines() if t.strip()]
    return [t for t in tags if t.startswith(INCREMENT_PREFIXES)]


def previous_tag(current: str) -> Optional[str]:
    tags = all_increment_tags()
    if current not in tags:
        return None
    idx = tags.index(current)
    if idx == 0:
        return None
    return tags[idx - 1]


def diff_between(prev: Optional[str], current: str) -> str:
    if not prev:
        return ""
    out = _git("--no-pager", "diff", f"{prev}..{current}")
    return out.strip()


def is_javafx_project(root: str = ".") -> bool:
    """Best-effort check for whether this project is a JavaFX (GUI) app.

    Adversarial CLI testing only works while the iP is still stdin-driven.
    From the A-Gui increment onwards the chatbot is a JavaFX window, so
    piping input does nothing and the runner just times out.
    """
    base = Path(root)
    for name in ("build.gradle", "build.gradle.kts"):
        path = base / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if "javafx" in text or "openjfx" in text:
            return True
    return False


def java_source_files(root: str = ".") -> list[Path]:
    """All Java source files under src/main/, excluding tests and build output."""
    base = Path(root)
    candidates: list[Path] = []
    for src_root in [base / "src" / "main" / "java", base / "src"]:
        if src_root.is_dir():
            candidates.extend(p for p in src_root.rglob("*.java") if "build" not in p.parts)
            break
    return sorted(set(candidates))


def read_file(path: Path, *, max_chars: int = 8000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + "\n// [truncated]\n"
    return text


def build_jar(timeout_seconds: int = 300) -> Optional[Path]:
    """Build the student's project as a runnable jar.

    Tries shadowJar first (the iP convention); falls back to the regular jar
    task. Returns the path to the produced jar, or None if no build script is
    present.
    """
    if not Path("build.gradle").exists() and not Path("build.gradle.kts").exists():
        return None

    gradle = "./gradlew" if Path("gradlew").exists() else "gradle"
    if gradle.startswith("./") and not os.access("gradlew", os.X_OK):
        os.chmod("gradlew", 0o755)

    for task in ("shadowJar", "jar"):
        try:
            subprocess.run(
                [gradle, task, "-q", "--console=plain"],
                check=True,
                timeout=timeout_seconds,
            )
        except subprocess.CalledProcessError:
            continue
        except subprocess.TimeoutExpired:
            return None
        jars = sorted(Path("build/libs").glob("*.jar"))
        if jars:
            return _pick_runnable_jar(jars)
    return None


def _pick_runnable_jar(jars: Iterable[Path]) -> Path:
    """Prefer the shadow/all jar over slim variants."""
    jars = list(jars)
    for j in jars:
        if "all" in j.name or "shadow" in j.name:
            return j
    return jars[0]


def run_jar(
    jar: Path,
    stdin_text: str,
    *,
    timeout_seconds: int = 15,
) -> tuple[str, str, int]:
    """Run the jar with the given stdin and return (stdout, stderr, exit_code).

    Exit code -1 indicates the process timed out.
    """
    try:
        result = subprocess.run(
            ["java", "-jar", str(jar)],
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        err = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        return out, err + "\n[process timed out]", -1
