"""GitHub REST API helpers used across the three modes.

We keep this minimal — issues and comments are all we need. If you find
yourself adding a third resource here, consider whether the new mode really
needs it.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import requests

API_BASE = "https://api.github.com"
TIMEOUT = 30


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def request(method: str, path: str, **kwargs):
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    response = requests.request(method, url, headers=_headers(), timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return None


def repo() -> str:
    name = os.environ.get("GITHUB_REPOSITORY")
    if not name:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    return name


def event_payload() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_issue_by_title(repo_name: str, title: str, state: str = "open") -> Optional[dict]:
    issues = request(
        "GET",
        f"/repos/{repo_name}/issues",
        params={"state": state, "per_page": 100},
    ) or []
    for issue in issues:
        if issue.get("title") == title:
            return issue
    return None


def create_issue(repo_name: str, title: str, body: str) -> dict:
    return request(
        "POST",
        f"/repos/{repo_name}/issues",
        json={"title": title, "body": body},
    )


def update_issue(repo_name: str, number: int, body: str) -> dict:
    return request(
        "PATCH",
        f"/repos/{repo_name}/issues/{number}",
        json={"body": body},
    )


def post_comment(repo_name: str, number: int, body: str) -> dict:
    return request(
        "POST",
        f"/repos/{repo_name}/issues/{number}/comments",
        json={"body": body},
    )
