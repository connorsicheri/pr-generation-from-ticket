#!/usr/bin/env python3
"""
AI PR Generator Tool – Gemini Edition
====================================
A CLI utility that reads a Jira ticket, uses **Google Gemini** to generate code
patches, and opens a pull request that references the issue.

Revision 2025‑07‑28 (b)
----------------------
• **Changed behaviour**: `gather_candidate_files` now *only* includes file paths
  explicitly referenced in the ticket description. No automatic fallback file
  sampling.
• Updated inline comments and docstring to reflect the simpler logic.

Environment variables
---------------------
JIRA_URL, JIRA_TOKEN, GITHUB_TOKEN, GEMINI_API_KEY (required)
Optional: GEMINI_MODEL (default "gemini-1.5-pro"), MAX_PROMPT_TOKENS (char budget).

Usage
-----
$ pip install jira PyGithub google-generativeai tiktoken
$ export JIRA_URL=… JIRA_TOKEN=… GITHUB_TOKEN=… GEMINI_API_KEY=…
$ python ai_pr_generator.py ENG-1234
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from textwrap import shorten
from typing import List, Dict, Tuple

import tiktoken  # for token accounting
import google.generativeai as genai  # pip install google-generativeai
from jira import JIRA  # pip install jira
from github import Github  # pip install PyGithub

# ---------------------------------------------------------------------------
# Jira helpers
# ---------------------------------------------------------------------------

def get_jira_client() -> JIRA:
    return JIRA(server=os.environ["JIRA_URL"], token_auth=os.environ["JIRA_TOKEN"])


def fetch_issue(jira: JIRA, issue_key: str):
    return jira.issue(issue_key)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run(cmd: List[str], cwd: str | Path | None = None):
    print("$", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def clone_and_branch(repo_url: str, branch_name: str, workdir: Path) -> Path:
    repo_path = workdir / "repo"
    run(["git", "clone", repo_url, str(repo_path)])
    run(["git", "checkout", "-b", branch_name], cwd=repo_path)
    return repo_path


def commit_push(repo_path: Path, branch_name: str, message: str):
    run(["git", "add", "-A"], cwd=repo_path)
    try:
        run(["git", "commit", "-m", message], cwd=repo_path)
    except subprocess.CalledProcessError:
        print("No changes to commit – exiting.")
        raise SystemExit(0)
    run(["git", "push", "-u", "origin", branch_name], cwd=repo_path)


# ---------------------------------------------------------------------------
# Data structures & helpers for AI step
# ---------------------------------------------------------------------------

class TicketContext:
    """Extract file paths (``path``) and free‑form instructions from a ticket."""

    def __init__(self, description: str):
        self.description = description or ""
        self.file_paths, self.instructions = self._parse(self.description)

    @staticmethod
    def _parse(text: str) -> Tuple[List[str], str]:
        file_regex = re.compile(r"`([^`\n]+\.(?:py|go|js|ts|tsx|java|yaml|json))`")
        paths = file_regex.findall(text)
        instructions = re.sub(file_regex, "", text).strip()
        return paths, instructions


# Token helper (roughly 4 chars per token when tiktoken unavailable)
_encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(txt: str) -> int:  # kept for potential future limits
    return len(_encoding.encode(txt))


def gather_candidate_files(repo_path: Path, hinted_paths: List[str], budget_chars: int = 6000) -> Dict[str, str]:
    """Return *only* the files explicitly referenced in the ticket.

    Each file is truncated to fit within `budget_chars` in total. No automatic
    discovery of additional repository context is performed.
    """
    selected: Dict[str, str] = {}
    per_file_budget = max(budget_chars // max(len(hinted_paths), 1), 1)

    for rel in hinted_paths:
        p = repo_path / rel
        if not p.exists():
            # Silently skip missing files – model can decide to create them.
            continue
        content = p.read_text("utf-8", errors="ignore")
        selected[rel] = shorten(content, width=per_file_budget, placeholder="\n…\n")
    return selected


# ---------------------------------------------------------------------------
# Gemini API integration
# ---------------------------------------------------------------------------

def call_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var missing.")
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    return response.text.strip()


def build_prompt(issue, ctx: TicketContext, repo_snippets: Dict[str, str]) -> str:
    prompt = (
        f"You are a senior software engineer tasked with implementing Jira ticket {issue.key}.\n\n"
        f"Ticket summary: {issue.fields.summary}\n\n"
        "Ticket description (user instructions):\n" + ctx.instructions + "\n\n"
        "Repository snippets (read‑only context):\n"
    )
    for path, content in repo_snippets.items():
        prompt += f"--- BEGIN FILE {path} ---\n{content}\n--- END FILE {path} ---\n"
    prompt += (
        "\nReturn ONLY valid JSON shaped as:\n"
        "{ \"patches\": [ { \"path\": \"relative/file\", \"content\": \"new content…\" }, … ] }\n"
        "No markdown fences, no commentary."
    )
    return prompt


def parse_json_patches(json_text: str) -> List[dict]:
    try:
        data = json.loads(json_text)
        return data.get("patches", [])
    except json.JSONDecodeError as e:
        raise ValueError("Malformed JSON from Gemini") from e


def generate_changes_with_ai(issue, repo_path: Path) -> List[dict]:
    ctx = TicketContext(issue.fields.description or "")
    repo_snippets = gather_candidate_files(
        repo_path,
        hinted_paths=ctx.file_paths,
        budget_chars=int(os.getenv("MAX_PROMPT_TOKENS", "6000")),
    )
    prompt = build_prompt(issue, ctx, repo_snippets)
    json_text = call_gemini(prompt)
    return parse_json_patches(json_text)


def apply_patches(changes: List[dict], repo_path: Path):
    for fc in changes:
        dst = repo_path / fc["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(fc["content"], encoding="utf-8")


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def create_pull_request(gh: Github, repo_full_name: str, branch: str, base: str, title: str, body: str):
    repo = gh.get_repo(repo_full_name)
    return repo.create_pull(title=title, body=body, head=branch, base=base)


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a PR from a Jira ticket using Gemini")
    parser.add_argument("issue_key", help="Jira issue key, e.g. ENG-1234")
    args = parser.parse_args()

    jira = get_jira_client()
    issue = fetch_issue(jira, args.issue_key)

    repo_url = issue.fields.customfield_12345  # Adjust to your Jira schema
    if not repo_url:
        raise ValueError("Ticket missing repository URL (custom field).")

    branch_name = f"ai/{issue.key.lower()}"
    base_branch = os.getenv("DEFAULT_BASE_BRANCH", "main")
    gh = Github(os.environ["GITHUB_TOKEN"])

    with tempfile.TemporaryDirectory(prefix="ai_pr_") as tmp:
        repo_path = clone_and_branch(repo_url, branch_name, Path(tmp))
        patches = generate_changes_with_ai(issue, repo_path)
        apply_patches(patches, repo_path)
        commit_push(repo_path, branch_name, f"{issue.key}: {issue.fields.summary}")

        parts = repo_url.rstrip(".git").split("/")[-2:]
        repo_full_name = "/".join(parts)
        pr = create_pull_request(
            gh,
            repo_full_name=repo_full_name,
            branch=branch_name,
            base=base_branch,
            title=issue.fields.summary,
            body=issue.fields.description or "Automated PR by Gemini bot.",
        )

    jira.add_comment
