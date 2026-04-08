#!/usr/bin/env python3
"""
AI-Powered Increment Reviewer for CS2103T iP

This script supports two GitHub Actions entry points:
- tag pushes create or update an issue for the increment review
- issue comments on that review thread receive an LLM follow-up reply
"""

import json
import os
import re
import subprocess
from typing import Optional

import requests
from groq import Groq

SCRIPT_DIR = os.path.dirname(__file__)
REQUIREMENTS_FILE = os.path.join(SCRIPT_DIR, "..", "requirements.json")

ISSUE_TITLE_PREFIX = "iP Increment Review:"
ISSUE_METADATA_MARKER = "<!-- ip-reviewer:"
MAX_DIFF_CHARS = 12000
MAX_THREAD_CHARS = 8000
MAX_REVIEW_CHARS = 4000


def load_requirements_db():
    """Load the requirements JSON file. Returns the 'increments' dict or {}."""
    try:
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data.get("increments", {})
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"Could not load requirements.json: {error}")
        return {}


REQUIREMENTS_DB = load_requirements_db()


def load_event_payload():
    """Load the current GitHub event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return {}

    with open(event_path, "r", encoding="utf-8") as file:
        return json.load(file)


def github_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("No GITHUB_TOKEN available")

    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_api_request(method, url, **kwargs):
    """Perform a GitHub API request and return the JSON response when present."""
    headers = kwargs.pop("headers", {})
    merged_headers = github_headers()
    merged_headers.update(headers)

    response = requests.request(method, url, headers=merged_headers, timeout=30, **kwargs)
    response.raise_for_status()

    if response.content:
        return response.json()
    return None


def get_current_tag():
    """Get the current tag from GITHUB_REF."""
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/"):
        return ref[len("refs/tags/"):]
    return None


def get_previous_tag(current_tag):
    """Get the previous tag in chronological order that matches our pattern."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)", "refs/tags"],
            capture_output=True,
            text=True,
            check=True,
        )
        tags = [tag.strip() for tag in result.stdout.strip().split("\n") if tag.strip()]
        matching_tags = [tag for tag in tags if tag.startswith(("Level-", "A-", "B-"))]

        try:
            current_index = matching_tags.index(current_tag)
            if current_index + 1 < len(matching_tags):
                return matching_tags[current_index + 1]
        except ValueError:
            return None
    except subprocess.CalledProcessError:
        return None

    return None


def get_git_diff(prev_tag, current_tag):
    """Get the git diff between two tags."""
    if not prev_tag:
        return "No previous tag found for diff."

    try:
        result = subprocess.run(
            ["git", "--no-pager", "diff", f"{prev_tag}..{current_tag}"],
            capture_output=True,
            text=True,
            check=True,
        )
        diff = result.stdout.strip()
        return diff or "No code changes found between the previous and current tag."
    except subprocess.CalledProcessError:
        return "Error: Could not generate diff."


def get_requirements_text(tag):
    """Return a formatted requirements string for the given tag."""
    entry = REQUIREMENTS_DB.get(tag)
    if not entry:
        return f"Error: No requirements found for tag '{tag}' in requirements.json"

    lines = [f"## {entry.get('title', tag)} (Week {entry.get('week', '?')})"]
    lines.append(f"\n{entry.get('description', '')}\n")

    requirements = entry.get("requirements", [])
    if requirements:
        lines.append("**Must implement:**")
        for requirement in requirements:
            lines.append(f"- {requirement}")

    constraints = entry.get("constraints", [])
    if constraints:
        lines.append("\n**Constraints / explicit don'ts:**")
        for constraint in constraints:
            lines.append(f"- {constraint}")

    hints = entry.get("hints", [])
    if hints:
        lines.append("\n**Hints:**")
        for hint in hints:
            lines.append(f"- {hint}")

    return "\n".join(lines)


def get_requirements_url(tag):
    """Return the official URL for the tag, or None."""
    entry = REQUIREMENTS_DB.get(tag)
    if entry and entry.get("url"):
        return entry["url"]
    return None


def truncate_text(text, max_chars):
    """Trim overly long text before sending it to the LLM."""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n[truncated]"


def call_llm(messages, model="llama-3.1-8b-instant"):
    """Call the configured Groq chat completion model."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Error calling LLM: GROQ_API_KEY is not configured."

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        return response.choices[0].message.content
    except Exception as error:  # pylint: disable=broad-except
        return f"Error calling LLM: {error}"


def build_initial_review(tag, requirements, diff):
    """Generate the initial increment review text."""
    system_prompt = (
        "You are an AI assistant helping with code review for a software engineering "
        "course project. Review code changes against the given increment requirements. "
        "Structure your response in exactly three sections: Requirements check, "
        "Observations, One thing done well. Never provide corrected code or complete "
        "solutions. Frame observations as questions or point to concepts."
    )

    user_prompt = f"""Please review the following code changes against the increment requirements.

Increment tag:
{tag}

Requirements:
{requirements}

Code changes (git diff):
{truncate_text(diff, MAX_DIFF_CHARS)}

Provide your review in exactly three sections:
- Requirements check
- Observations
- One thing done well"""

    return call_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )


def build_follow_up_reply(tag, issue_body, comment_body):
    """Generate an LLM reply to a student comment in the review issue."""
    system_prompt = (
        "You are the follow-up assistant for an automated code review issue in a "
        "software engineering course. Answer the student's latest comment helpfully "
        "and conversationally, but do not provide corrected code or full solutions. "
        "Prefer hints, clarifying questions, and conceptual guidance grounded in the "
        "increment requirements and earlier review context."
    )

    user_prompt = f"""The following GitHub issue is the review thread for increment {tag}.

Issue body:
{truncate_text(issue_body, MAX_THREAD_CHARS)}

Latest student comment:
{truncate_text(comment_body, MAX_THREAD_CHARS)}

Write a concise reply that:
- answers the student's question or acknowledges their update
- stays grounded in the increment requirements and prior review context
- does not provide corrected code or a full solution
- suggests the next thing they should check if useful"""

    return call_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )


def build_issue_metadata(metadata):
    """Serialize hidden issue metadata into an HTML comment."""
    return f"{ISSUE_METADATA_MARKER}{json.dumps(metadata, separators=(',', ':'))} -->"


def parse_issue_metadata(body):
    """Parse hidden issue metadata from the issue body."""
    if not body:
        return {}

    match = re.search(r"<!-- ip-reviewer:(.*?) -->", body, re.DOTALL)
    if not match:
        return {}

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def issue_title_for(tag):
    return f"{ISSUE_TITLE_PREFIX} {tag}"


def build_issue_body(tag, previous_tag, sha, requirements_url, review_text):
    """Create the issue body for a fresh increment review issue."""
    metadata = {
        "tag": tag,
        "sha": sha,
        "previous_tag": previous_tag,
        "requirements_url": requirements_url,
    }

    context_lines = [
        f"## {issue_title_for(tag)}",
        "",
        f"- Tag: `{tag}`",
        f"- Commit: `{sha}`",
    ]
    if previous_tag:
        context_lines.append(f"- Previous tag: `{previous_tag}`")
    if requirements_url:
        context_lines.append(f"- Requirements: [Official requirements for {tag}]({requirements_url})")

    context_lines.extend(
        [
            "",
            "### Automated review",
            "",
            truncate_text(review_text, MAX_REVIEW_CHARS),
            "",
            "_This is an automated review. It may not be 100% accurate. Use your own judgement and ask your TA if unsure._",
            "",
            "Reply in this issue if you want the reviewer to clarify or discuss a point.",
            "",
            build_issue_metadata(metadata),
        ]
    )

    return "\n".join(context_lines)


def find_existing_issue(repo, title):
    """Find an open issue by exact title."""
    url = f"https://api.github.com/repos/{repo}/issues"
    issues = github_api_request(
        "GET",
        url,
        params={"state": "open", "creator": "github-actions[bot]", "per_page": 100},
    )

    for issue in issues or []:
        if issue.get("title") == title:
            return issue
    return None


def create_or_update_review_issue(tag, previous_tag, sha, review_text):
    """Create a new issue for the review or update the existing one for that tag."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("Missing GITHUB_REPOSITORY")

    title = issue_title_for(tag)
    requirements_url = get_requirements_url(tag)
    body = build_issue_body(tag, previous_tag, sha, requirements_url, review_text)
    existing_issue = find_existing_issue(repo, title)

    if existing_issue:
        update_url = f"https://api.github.com/repos/{repo}/issues/{existing_issue['number']}"
        github_api_request("PATCH", update_url, json={"body": body})
        print(f"Updated issue #{existing_issue['number']} for {tag}")
        return existing_issue["number"]

    create_url = f"https://api.github.com/repos/{repo}/issues"
    issue = github_api_request(
        "POST",
        create_url,
        json={
            "title": title,
            "body": body,
        },
    )
    print(f"Created issue #{issue['number']} for {tag}")
    return issue["number"]


def post_issue_comment(repo, issue_number, body):
    """Post a comment to an issue."""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    github_api_request("POST", url, json={"body": body})
    print(f"Posted comment to issue #{issue_number}")


def is_review_issue(issue):
    """Check whether the current issue is managed by the increment reviewer."""
    title = issue.get("title", "")
    body = issue.get("body", "")
    return title.startswith(ISSUE_TITLE_PREFIX) and ISSUE_METADATA_MARKER in body


def is_bot_comment(comment):
    """Ignore comments created by bots to avoid reply loops."""
    user = comment.get("user", {})
    return user.get("type") == "Bot"


def extract_tag_from_issue(issue):
    """Get the increment tag from issue metadata or title."""
    metadata = parse_issue_metadata(issue.get("body", ""))
    if metadata.get("tag"):
        return metadata["tag"]

    title = issue.get("title", "")
    if title.startswith(ISSUE_TITLE_PREFIX):
        return title[len(ISSUE_TITLE_PREFIX):].strip()
    return None


def handle_tag_push():
    """Create or update the issue-based review for a pushed increment tag."""
    current_tag = get_current_tag()
    if not current_tag:
        print("No tag found in GITHUB_REF")
        return

    if current_tag not in REQUIREMENTS_DB:
        print(f"Tag {current_tag} not found in requirements.json")
        return

    sha = os.environ.get("GITHUB_SHA")
    if not sha:
        raise RuntimeError("Missing GITHUB_SHA")

    previous_tag = get_previous_tag(current_tag)
    diff = get_git_diff(previous_tag, current_tag)
    requirements = get_requirements_text(current_tag)

    if requirements.startswith("Error:"):
        review_text = (
            f"Could not load requirements: {requirements}\n\n"
            f"Diff summary:\n{truncate_text(diff, 1000)}"
        )
    else:
        review_text = build_initial_review(current_tag, requirements, diff)

    create_or_update_review_issue(current_tag, previous_tag, sha, review_text)


def handle_issue_comment():
    """Reply to a student comment in an increment review issue."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("Missing GITHUB_REPOSITORY")

    payload = load_event_payload()
    action = payload.get("action")
    issue = payload.get("issue", {})
    comment = payload.get("comment", {})

    if action != "created":
        print(f"Ignoring issue_comment action: {action}")
        return

    if not is_review_issue(issue):
        print("Ignoring comment on a non-review issue")
        return

    if is_bot_comment(comment):
        print("Ignoring bot comment")
        return

    tag = extract_tag_from_issue(issue)
    if not tag:
        print("Could not determine increment tag from issue")
        return

    reply_text = build_follow_up_reply(tag, issue.get("body", ""), comment.get("body", ""))
    post_issue_comment(repo, issue["number"], reply_text)


def main():
    event_name = os.environ.get("GITHUB_EVENT_NAME")

    if event_name == "push":
        handle_tag_push()
        return

    if event_name == "issue_comment":
        handle_issue_comment()
        return

    print(f"Unsupported event: {event_name}")


if __name__ == "__main__":
    main()
