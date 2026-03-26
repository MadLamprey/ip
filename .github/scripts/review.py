#!/usr/bin/env python3
"""
AI-Powered Increment Reviewer for CS2103T iP

This script is triggered on tag pushes and posts automated code reviews
as GitHub commit comments.
"""

import os
import subprocess
import requests
from groq import Groq
import json

REQUIREMENTS_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'requirements.json'
)

def load_requirements_db():
    """Load the requirements JSON file. Returns the 'increments' dict or {}."""
    try:
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('increments', {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Could not load requirements.json: {e}")
        return {}

REQUIREMENTS_DB = load_requirements_db()

def get_current_tag():
    """Get the current tag from GITHUB_REF"""
    ref = os.environ.get('GITHUB_REF', '')
    if ref.startswith('refs/tags/'):
        return ref[len('refs/tags/'):]
    return None

def get_previous_tag(current_tag):
    """Get the previous tag in chronological order that matches our pattern"""
    try:
        # Get all tags sorted by creation date (newest first)
        result = subprocess.run(['git', 'for-each-ref', '--sort=-creatordate', '--format="%(refname:short)"', 'refs/tags'],
                              capture_output=True, text=True, check=True)
        print(f"DEBUG all tags:\n{result.stdout}")
        tags = [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]

        # Filter to only tags that match our pattern
        matching_tags = [tag for tag in tags if tag.startswith(('Level-', 'A-', 'B-'))]
        print(f"DEBUG matching tags: {matching_tags}") 
        # Find current tag and return the next one (which is older)
        try:
            current_index = matching_tags.index(current_tag)
            if current_index + 1 < len(matching_tags):
                return matching_tags[current_index + 1]
        except ValueError:
            pass
    except subprocess.CalledProcessError:
        pass
    return None

def get_git_diff(prev_tag, current_tag):
    """Get the git diff between two tags"""
    try:
        result = subprocess.run(['git', 'diff', '--no-pager', f'{prev_tag}..{current_tag}'],
                              capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return "Error: Could not generate diff"

def get_requirements_text(tag):
    """
    Return a formatted requirements string for the given tag.
    Loads from requirements.json. Returns an error string if not found.
    """
    entry = REQUIREMENTS_DB.get(tag)
    if not entry:
        return f"Error: No requirements found for tag '{tag}' in requirements.json"

    lines = [f"## {entry.get('title', tag)} (Week {entry.get('week', '?')})"]
    lines.append(f"\n{entry.get('description', '')}\n")

    reqs = entry.get('requirements', [])
    if reqs:
        lines.append("**Must implement:**")
        for r in reqs:
            lines.append(f"- {r}")

    constraints = entry.get('constraints', [])
    if constraints:
        lines.append("\n**Constraints / explicit don'ts:**")
        for c in constraints:
            lines.append(f"- {c}")

    hints = entry.get('hints', [])
    if hints:
        lines.append("\n**Hints:**")
        for h in hints:
            lines.append(f"- {h}")

    return '\n'.join(lines)


def get_requirements_url(tag):
    """Return the official URL for the tag, or None."""
    entry = REQUIREMENTS_DB.get(tag)
    if entry and entry.get('url'):
        return entry['url']
    return None


def call_llm(requirements, diff):
    """Call Groq LLM for code review"""
    client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

    system_prompt = """You are an AI assistant helping with code review for a software engineering course project. Your task is to review code changes against given requirements. Structure your response in three sections: Requirements check, Observations, One thing done well. Never provide corrected code or complete solutions. Frame observations as questions or point to concepts."""

    user_prompt = f"""Please review the following code changes against the increment requirements.

Requirements:
{requirements}

Code changes (git diff):
{diff}

Provide your review in exactly three sections:
- Requirements check
- Observations
- One thing done well"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Using Llama 3 8B model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling LLM: {e}"

def post_github_comment(review_text, tag):
    """Post the review as a GitHub commit comment"""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("No GITHUB_TOKEN available")
        return

    # Get repo info from environment
    repo = os.environ.get('GITHUB_REPOSITORY')
    sha = os.environ.get('GITHUB_SHA')

    if not repo or not sha:
        print("Missing repo or SHA info")
        return

    url = f"https://api.github.com/repos/{repo}/commits/{sha}/comments"

    req_url = get_requirements_url(tag)
    ref_line = f"\n📖 [Official requirements for {tag}]({req_url})" if req_url else ""

    comment_body = f"""## 🤖 iP Increment Review — `{tag}`

{review_text}
{ref_line}
*This is an automated review. It may not be 100% accurate — use your own judgement and ask your TA if unsure.*"""

    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    try:
        response = requests.post(url, headers=headers, json={'body': comment_body})
        response.raise_for_status()
        print("Comment posted successfully")
    except requests.RequestException as e:
        print(f"Error posting comment: {e}")

def main():
    current_tag = get_current_tag()
    if not current_tag:
        print("No tag found in GITHUB_REF")
        return

    if current_tag not in REQUIREMENTS_DB:
        print(f"Tag {current_tag} not found in requirements.json")
        return

    print(f"Processing review for tag: {current_tag}")

    prev_tag = get_previous_tag(current_tag)
    if not prev_tag:
        print("Could not find previous tag")
        diff = "No previous tag found for diff"
    else:
        print(f"Previous tag: {prev_tag}")
        diff = get_git_diff(prev_tag, current_tag)

    requirements = get_requirements_text(current_tag)

    if requirements.startswith("Error"):
        review = f"Could not load requirements: {requirements}\n\nDiff summary:\n{diff[:500]}..."
    else:
        review = call_llm(requirements, diff)

    post_github_comment(review, current_tag)

if __name__ == "__main__":
    main()