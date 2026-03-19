#!/usr/bin/env python3
"""
AI-Powered Increment Reviewer for CS2103T iP

This script is triggered on tag pushes and posts automated code reviews
as GitHub commit comments.
"""

import os
import subprocess
import requests
from bs4 import BeautifulSoup
from groq import Groq
import json

# Mapping of increment tags to their requirement URLs and anchors
TAG_REQUIREMENTS = {
    # Week 2 increments
    'Level-0': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-0-rename-greet-exit'),
    'Level-1': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-1-echo'),
    'Level-2': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-2-add-list'),
    'Level-3': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-3-mark-as-done'),
    'Level-4': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-4-todo-event-deadline'),
    'A-TextUiTesting': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-a-textuitesting-automated-text-ui-testing'),
    'Level-5': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-5-handle-errors'),
    'Level-6': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-level-6-delete'),
    'A-Enums': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week2/project.html', 'duke-a-enums-enums'),

    # Week 3 increments
    'Level-7': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-level-7-save'),
    'Level-8': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-level-8-dates-and-times'),
    'A-MoreOOP': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-moreoop-use-more-oop'),
    'A-Packages': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-packages-organize-into-packages'),
    'A-Gradle': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-gradle-use-gradle'),
    'A-JUnit': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-junit'),
    'A-Jar': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-jar-create-a-jar-file'),
    'A-JavaDoc': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-javadoc-javadoc'),
    'A-CodingStandard': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-a-codingstandard-follow-the-coding-standard'),
    'Level-9': ('https://nus-cs2103-ay2526-s2.github.io/website/schedule/week3/project.html', 'duke-level-9-find'),
}

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
        tags = [tag.strip('"') for tag in result.stdout.strip().split('\n') if tag.strip()]

        # Filter to only tags that match our pattern
        matching_tags = [tag for tag in tags if tag.startswith(('Level-', 'A-', 'B-'))]

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

def fetch_requirements(url, anchor):
    """Fetch the requirements text from the course website"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        section = soup.find(id=anchor)

        if not section:
            return f"Error: Could not find requirements section with id '{anchor}'"

        # Extract text from the section until the next duke- section
        content = []
        for element in section.find_all_next(['p', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote']):
            if element.find_parent() and element.find_parent().get('id') and element.find_parent().get('id') != anchor:
                parent_id = element.find_parent().get('id')
                if parent_id and parent_id.startswith('duke-') and parent_id != anchor:
                    break
            text = element.get_text(separator=' ', strip=True)
            if text:
                content.append(text)

        text = ' '.join(content)
        return text[:2000]  # Limit to reasonable length

    except requests.RequestException as e:
        return f"Error fetching requirements: {e}"

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
            model="llama3-8b-8192",  # Using Llama 3 8B model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
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

    comment_body = f"""## 🤖 iP Increment Review — `{tag}`

{review_text}

📖 [Official requirements for {tag}]({TAG_REQUIREMENTS[tag][0]}#{TAG_REQUIREMENTS[tag][1]})

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

    if current_tag not in TAG_REQUIREMENTS:
        print(f"Tag {current_tag} not in requirements mapping")
        return

    print(f"Processing review for tag: {current_tag}")

    prev_tag = get_previous_tag(current_tag)
    if not prev_tag:
        print("Could not find previous tag")
        diff = "No previous tag found for diff"
    else:
        print(f"Previous tag: {prev_tag}")
        diff = get_git_diff(prev_tag, current_tag)

    url, anchor = TAG_REQUIREMENTS[current_tag]
    requirements = fetch_requirements(url, anchor)

    if requirements.startswith("Error"):
        review = f"Could not fetch requirements: {requirements}\n\nDiff summary:\n{diff[:500]}..."
    else:
        review = call_llm(requirements, diff)

    post_github_comment(review, current_tag)

if __name__ == "__main__":
    main()