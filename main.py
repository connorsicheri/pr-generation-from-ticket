#!/usr/bin/env python3
"""
AI PR Generator Tool
====================
A CLI utility that reads a Jira ticket, uses an LLM to generate code patches,
and opens a pull request that references the issue.

Changes in this revision (2025‑07‑28)
------------------------------------
• **generate_changes_with_ai** fleshed out: now does ticket‑parsing, file discovery
  and prompt construction, leaving only the model call & diff parsing to fill in.
• Added helper utilities (`TicketContext`, `gather_candidate_files`, etc.).
• Outlined minimal OpenAI call (can be swapped for Anthropic / local model).
• Added dependency guard imports & explicit type hints.

Environment variables
---------------------
JIRA_URL, JIRA_TOKEN, GITHUB_TOKEN as before plus:
OPENAI_MODEL          – model name (e.g. "gpt-4o-mini")
MAX_PROMPT_TOKENS     – budget for repo context (default 6 000 chars)

Usage
-----
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

import tiktoken  # optional, for token counting (pip install tiktoken)

try:
    import openai  # pip install openai
except ImportError:  # keep hard dependency optional for test harness
    openai = None  # type: ignore

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
    """Hold structured info extracted from the Jira description."""

    def __init__(self, description: str):
        self.description = description
        self.file_paths, self.instructions = self._parse(description)

    @staticmethod
    def _parse(text: str) -> Tuple[List[str], str]:
        """Very lightweight parse: look for markdown code fences listing paths
        and capture the rest as free‑form instructions."""
        file_regex = re.compile(r"`([^`\n]+\.(?:py|go|js|ts|tsx|java|yaml|json))`")
        paths = file_regex.findall(text)
        # strip code blocks for instruction body
        instructions = re.sub(file_regex, "", text)
        return paths, instructions.strip()


# Token helper (quick approximation)
_encoding = tiktoken.get_encoding("cl100k_base") if "tiktoken" in globals() else None

def count_tokens(txt: str) -> int:
    if _encoding:
        return len(_encoding.encode(txt))
    return len(txt) // 4  # rough estimate


def gather_candidate_files(repo_path: Path, hinted_paths: List[str], budget_chars: int = 6000) -> Dict[str, str]:
    """Return {relative_path: truncated_content} respecting char budget."""
    selected: Dict[str, str] = {}

    # 1. Explicit paths from ticket take priority
    for rel in hinted_paths:
        p = repo_path / rel
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="ignore")
            selected[rel] = shorten(content, width=budget_chars // 2, placeholder="\n…\n")
            budget_chars -= len(selected[rel])
            if budget_chars <= 0:
                return selected

    # 2. Fallback: heuristically sample small files (<400 lines) modified recently
    for p in repo_path.rglob("*.*"):
        if p.suffix not in {".py", ".go", ".js", ".ts", ".tsx", ".yaml", ".json"}:
            continue
        if p.is_dir() or p.name.startswith("."):
            continue
        if p.as_posix() in selected:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if len(text) > 10_000:
            continue  # skip huge blobs
        selected[p.relative_to(repo_path).as_posix()] = shorten(text, width=budget_chars // 2, placeholder="\n…\n")
        budget_chars -= len(selected[p.relative_to(repo_path).as_posix()])
        if budget_chars <= 0:
            break
    return selected


# ---------------------------------------------------------------------------
# AI‑powered code generation
# ---------------------------------------------------------------------------

def build_prompt(issue, ctx: TicketContext, repo_snippets: Dict[str, str]) -> str:
    """Compose a single prompt string for the model."""
    header = (
        f"You are a senior software engineer tasked with implementing Jira ticket {issue.key}.\n\n"
        f"Ticket summary: {issue.fields.summary}\n\n"
        "Ticket description (user instructions):\n" + ctx.instructions + "\n\n"
        "Repository snippets (read‑only):\n"
    )
    for path, content in repo_snippets.items():
        header += f"--- BEGIN FILE {path} ---\n{content}\n--- END FILE {path} ---\n"
    header += (
        "\nReturn the **minimal** set of file changes as valid JSON in the shape:\n"
        "{\n  \"patches\": [\n    {\"path\": \"relative/file.py\", \"content\": \"full new file content…\"},\n    …\n  ]\n}\n"
        "Do not wrap the JSON in markdown fences; no other commentary."
    )
    return header


def call_openai(prompt: str) -> str:
    if openai is None:
        raise RuntimeError("openai package not available – install or stub.")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


def parse_json_patches(json_text: str) -> List[dict]:
    """Convert model JSON string into list[dict]."""
    try:
        data = json.loads(json_text)
        return data.get("patches", [])
    except json.JSONDecodeError as e:
        raise ValueError("Malformed JSON from model") from e


def generate_changes_with_ai(issue, repo_path: Path) -> List[dict]:
    """High‑level orchestration for file discovery → prompt → patches."""
    description = issue.fields.description or ""
    ctx = TicketContext(description)

    repo_snippets = gather_candidate_files(
        repo_path,
        hinted_paths=ctx.file_paths,
        budget_chars=int(os.getenv("MAX_PROMPT_TOKENS", "6000")),
    )

    prompt = build_prompt(issue, ctx, repo_snippets)

    # ––– Call the LLM –––
    json_text = call_openai(prompt)

    patches = parse_json_patches(json_text)
    return patches


def apply_patches(changes: List[dict], repo_path: Path):
    for file_change in changes:
        dst = repo_path / file_change["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(file_change["content"], encoding="utf-8")


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
    parser = argparse.ArgumentParser(description="Generate a PR from a Jira ticket using AI")
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

        # Convert repo_url to "owner/name"
        parts = repo_url.rstrip(".git").split("/")[-2:]
        repo_full_name = "/".join(parts)
        pr = create_pull_request(
            gh,
            repo_full_name=repo_full_name,
            branch=branch_name,
            base=base_branch,
            title=issue.fields.summary,
            body=issue.fields.description or "Automated PR by AI bot.",
        )

    jira.add_comment(issue, f"PR opened: {pr.html_url}")
    print("Pull request created:", pr.html_url)


if __name__ == "__main__":
    main()
