from __future__ import annotations

import os
from github import Github
from typing import Any, Dict, List, Optional
import json


def get_github_client() -> Github:
    token = os.environ["GITHUB_TOKEN"]
    return Github(token)


def create_pull_request(gh: Github, repo_full_name: str, branch: str, base: str, title: str, body: str):
    print(f"🔄 Creating pull request...")
    print(f"   📁 Repository: {repo_full_name}")
    print(f"   🌿 Source branch: {branch}")
    print(f"   🌿 Target branch: {base}")
    print(f"   🏷️ Title: {title}")
    repo = gh.get_repo(repo_full_name)
    pr = repo.create_pull(title=title, body=body, head=branch, base=base)
    print(f"   ✅ Pull request created: #{pr.number}")
    print(f"   🔗 URL: {pr.html_url}")
    return pr


# --- Reviewer loop helpers ---

AI_STATE_MARKER = "[AI-REVIEW-STATE]"


def request_reviewers(pr, reviewers: List[str]) -> None:
    """Request reviewers on a PR. Ignores errors (e.g., names not in org)."""
    try:
        if not reviewers:
            return
        # GitHub API: request_reviewers(users=[..])
        pr.create_review_request(reviewers=reviewers)
    except Exception as e:
        print(f"ℹ️  Failed to request reviewers: {e}")
AI_SUMMARY_HEADER = "[AI Review Loop]"


def find_open_pr(repo, desired_branch_prefix: str, expected_title: Optional[str] = None):
    """Find an open PR whose head ref starts with the desired prefix and (optionally) matches title."""
    for pr in repo.get_pulls(state="open"):
        try:
            head_ok = pr.head and pr.head.ref and pr.head.ref.startswith(desired_branch_prefix)
            title_ok = True if expected_title is None else (pr.title == expected_title)
            if head_ok and title_ok:
                return pr
        except Exception:
            continue
    return None


def post_pr_comment(pr, body: str) -> None:
    try:
        pr.create_issue_comment(body)
    except Exception as e:
        print(f"ℹ️  Failed to post PR comment: {e}")


def get_pr_changed_files(pr, limit: int = 200) -> List[str]:
    """Return list of changed file paths in a PR (head vs base)."""
    files: List[str] = []
    try:
        for f in pr.get_files():
            files.append(getattr(f, "filename", ""))
            if len(files) >= limit:
                break
    except Exception as e:
        print(f"ℹ️  Failed to list PR files: {e}")
    return files


def build_iteration_summary_comment(
    iteration: int,
    outcome: str,
    comments_count: int,
    suggestions_count: int,
    changed_files: Optional[List[str]],
    branch: str,
    auto_approved: bool = False,
    state: Optional[Dict[str, Any]] = None,
) -> str:
    changed_files = changed_files or []
    header = f"{AI_SUMMARY_HEADER} Iteration {iteration}\n"
    auto = " (auto-approved due to trivial comments)" if auto_approved else ""
    lines: List[str] = [
        header,
        f"Outcome: {outcome}{auto}",
        f"Branch: {branch}",
        f"Comments: {comments_count} | Suggestions: {suggestions_count}",
        f"Changed files ({len(changed_files)}):",
    ]
    preview = changed_files[:10]
    for p in preview:
        lines.append(f"- {p}")
    if len(changed_files) > len(preview):
        lines.append(f"- … and {len(changed_files) - len(preview)} more")
    if state is not None:
        try:
            state_text = json.dumps(state, indent=2, ensure_ascii=False)
        except Exception:
            state_text = json.dumps({"error": "state serialization failed"})
        lines.append("")
        lines.append(AI_STATE_MARKER)
        lines.append("```json")
        lines.append(state_text)
        lines.append("```")
    return "\n".join(lines)


def read_latest_ai_state_from_comments(pr) -> Optional[Dict[str, Any]]:
    """Scan PR issue comments newest-to-oldest for the AI state marker and return parsed JSON state."""
    try:
        comments = list(pr.get_issue_comments())
    except Exception as e:
        print(f"ℹ️  Could not list PR comments: {e}")
        return None
    for c in reversed(comments):
        body = (getattr(c, "body", "") or "")
        if AI_STATE_MARKER in body:
            # find the json code block after the marker
            marker_index = body.find(AI_STATE_MARKER)
            json_block_index = body.find("```json", marker_index)
            if json_block_index == -1:
                continue
            json_start = json_block_index + len("```json")
            json_end = body.find("```", json_start)
            if json_end == -1:
                continue
            json_text = body[json_start:json_end].strip()
            try:
                return json.loads(json_text)
            except Exception:
                continue
    return None
