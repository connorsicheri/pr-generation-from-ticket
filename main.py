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
    print("🔗 Connecting to Jira...")
    jira_url = os.environ["JIRA_URL"]
    jira_email = os.environ["JIRA_EMAIL"]
    jira_token = os.environ["JIRA_TOKEN"]
    print(f"   Server: {jira_url}")
    print(f"   Email: {jira_email}")
    print(f"   Token: {jira_token[:10]}...{jira_token[-4:]} (masked)")
    
    # Use basic auth (email + token) for Jira Cloud
    print("   Using basic authentication (email + token)...")
    return JIRA(server=jira_url, basic_auth=(jira_email, jira_token))


def fetch_issue(jira: JIRA, issue_key: str):
    print(f"📋 Fetching Jira issue: {issue_key}")
    issue = jira.issue(issue_key)
    print(f"   ✅ Found issue: {issue.fields.summary}")
    print(f"   📝 Description length: {len(issue.fields.description or '')} characters")
    return issue


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run(cmd: List[str], cwd: str | Path | None = None):
    print(f"💻 Running: {' '.join(cmd)}")
    if cwd:
        print(f"   📁 Working directory: {cwd}")
    try:
        subprocess.check_call(cmd, cwd=cwd)
        print("   ✅ Command completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Command failed with exit code {e.returncode}")
        raise


def clone_and_branch(repo_url: str, branch_name: str, workdir: Path) -> Path:
    print(f"🔄 Cloning repository...")
    print(f"   🔗 Repository: {repo_url}")
    print(f"   🌿 Branch: {branch_name}")
    print(f"   📁 Temporary directory: {workdir}")
    
    repo_path = workdir / "repo"
    run(["git", "clone", repo_url, str(repo_path)])
    run(["git", "checkout", "-b", branch_name], cwd=repo_path)
    
    print(f"   ✅ Repository cloned and branch created")
    return repo_path


def commit_push(repo_path: Path, branch_name: str, message: str):
    print(f"💾 Committing and pushing changes...")
    print(f"   📝 Commit message: {message}")
    print(f"   🌿 Target branch: {branch_name}")
    
    run(["git", "add", "-A"], cwd=repo_path)
    try:
        run(["git", "commit", "-m", message], cwd=repo_path)
    except subprocess.CalledProcessError:
        print("⚠️  No changes to commit – exiting.")
        raise SystemExit(0)
    run(["git", "push", "-u", "origin", branch_name], cwd=repo_path)
    print("   ✅ Changes committed and pushed successfully")


# ---------------------------------------------------------------------------
# Data structures & helpers for AI step
# ---------------------------------------------------------------------------

class TicketContext:
    """Extract file paths (``path``) and free‑form instructions from a ticket."""

    def __init__(self, description: str):
        self.description = description or ""
        print(f"🔍 Parsing ticket description...")
        self.file_paths, self.instructions = self._parse(self.description)
        print(f"   📁 Found {len(self.file_paths)} file(s): {self.file_paths}")
        print(f"   📝 Instructions length: {len(self.instructions)} characters")

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
    print(f"📂 Gathering candidate files...")
    print(f"   📊 Character budget: {budget_chars}")
    print(f"   📁 Files to examine: {hinted_paths}")
    
    selected: Dict[str, str] = {}
    per_file_budget = max(budget_chars // max(len(hinted_paths), 1), 1)
    print(f"   📄 Per-file budget: {per_file_budget} characters")

    for rel in hinted_paths:
        p = repo_path / rel
        if not p.exists():
            print(f"   ⚠️  File not found: {rel} (will be created by AI)")
            continue
        content = p.read_text("utf-8", errors="ignore")
        original_length = len(content)
        truncated_content = shorten(content, width=per_file_budget, placeholder="\n…\n")
        selected[rel] = truncated_content
        print(f"   ✅ Loaded {rel}: {original_length} → {len(truncated_content)} chars")
    
    print(f"   📁 Total files loaded: {len(selected)}")
    return selected


# ---------------------------------------------------------------------------
# Gemini API integration
# ---------------------------------------------------------------------------

def call_gemini(prompt: str) -> str:
    print(f"🤖 Calling Gemini AI...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var missing.")
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    print(f"   🧠 Model: {model_name}")
    print(f"   📝 Prompt length: {len(prompt)} characters")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    print("   🔄 Generating content...")
    response = model.generate_content(prompt)
    result = response.text.strip()
    
    print(f"   ✅ Response received: {len(result)} characters")
    print(f"   🔍 First 100 chars: {result[:100]}...")
    return result


def build_prompt(issue, ctx: TicketContext, repo_snippets: Dict[str, str]) -> str:
    print(f"📝 Building AI prompt...")
    print(f"   🎫 Ticket: {issue.key} - {issue.fields.summary}")
    print(f"   📁 Files in context: {len(repo_snippets)}")
    
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
    
    print(f"   📊 Final prompt length: {len(prompt)} characters")
    return prompt


def parse_json_patches(json_text: str) -> List[dict]:
    print(f"🔍 Parsing AI response...")
    try:
        data = json.loads(json_text)
        patches = data.get("patches", [])
        print(f"   ✅ Successfully parsed {len(patches)} patches")
        for i, patch in enumerate(patches):
            print(f"     {i+1}. {patch.get('path', 'unknown')} ({len(patch.get('content', ''))} chars)")
        return patches
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON parsing failed: {e}")
        print(f"   🔍 Raw response: {json_text[:500]}...")
        raise ValueError("Malformed JSON from Gemini") from e


def generate_changes_with_ai(issue, repo_path: Path) -> List[dict]:
    print(f"🧠 Generating changes with AI...")
    
    # Parse ticket context
    ctx = TicketContext(issue.fields.description or "")
    print()
    
    # Gather file context
    budget_chars = int(os.getenv("MAX_PROMPT_TOKENS", "6000"))
    repo_snippets = gather_candidate_files(
        repo_path,
        hinted_paths=ctx.file_paths,
        budget_chars=budget_chars,
    )
    print()
    
    # Build and send prompt
    prompt = build_prompt(issue, ctx, repo_snippets)
    json_text = call_gemini(prompt)
    print()
    
    # Parse response
    patches = parse_json_patches(json_text)
    print()
    
    return patches


def apply_patches(changes: List[dict], repo_path: Path):
    print(f"💾 Applying patches...")
    for i, fc in enumerate(changes):
        file_path = fc["path"]
        content = fc["content"]
        dst = repo_path / file_path
        
        print(f"   {i+1}. Writing {file_path} ({len(content)} characters)")
        
        # Create directory if it doesn't exist
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        dst.write_text(content, encoding="utf-8")
        
        print(f"      ✅ File written successfully")
    
    print(f"   🎉 All {len(changes)} patches applied successfully")


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    print("🎆 AI PR Generator Starting...")
    print("=" * 50)
    
    parser = argparse.ArgumentParser(description="Generate a PR from a Jira ticket using Gemini")
    parser.add_argument("issue_key", help="Jira issue key, e.g. ENG-1234")
    args = parser.parse_args()
    
    print(f"🎫 Processing ticket: {args.issue_key}")
    print()

    # Step 1: Connect to Jira and fetch issue
    print("📄 STEP 1: Fetching Jira ticket")
    print("-" * 30)
    jira = get_jira_client()
    issue = fetch_issue(jira, args.issue_key)
    print()

    # Step 2: Extract repository information
    print("📄 STEP 2: Extracting repository information")
    print("-" * 30)
    repo_url = issue.fields.customfield_12345  # Adjust to your Jira schema
    if not repo_url:
        print("❌ Error: Ticket missing repository URL (custom field).")
        raise ValueError("Ticket missing repository URL (custom field).")
    
    print(f"📁 Repository URL: {repo_url}")
    branch_name = f"ai/{issue.key.lower()}"
    base_branch = os.getenv("DEFAULT_BASE_BRANCH", "main")
    print(f"🌿 New branch: {branch_name}")
    print(f"🌿 Base branch: {base_branch}")
    print()

    # Step 3: Setup GitHub client
    print("📄 STEP 3: Connecting to GitHub")
    print("-" * 30)
    gh = Github(os.environ["GITHUB_TOKEN"])
    print("✅ GitHub client initialized")
    print()

    # Step 4: Process in temporary directory
    print("📄 STEP 4: Processing changes")
    print("-" * 30)
    with tempfile.TemporaryDirectory(prefix="ai_pr_") as tmp:
        print(f"📁 Using temporary directory: {tmp}")
        
        # Clone repository and create branch
        repo_path = clone_and_branch(repo_url, branch_name, Path(tmp))
        print()
        
        # Generate AI changes
        print("🤖 Generating AI changes...")
        patches = generate_changes_with_ai(issue, repo_path)
        print()
        
        # Apply patches
        apply_patches(patches, repo_path)
        print()
        
        # Commit and push
        commit_message = f"{issue.key}: {issue.fields.summary}"
        commit_push(repo_path, branch_name, commit_message)
        print()

        # Step 5: Create pull request
        print("📄 STEP 5: Creating pull request")
        print("-" * 30)
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
        print()

    # Final success message
    print("🎉 SUCCESS!")
    print("=" * 50)
    print(f"✅ Pull request created: #{pr.number}")
    print(f"🔗 URL: {pr.html_url}")
    print(f"🌿 Branch: {branch_name}")
    print(f"🎫 Ticket: {args.issue_key}")
    print()
    print("👍 Your AI-generated pull request is ready for review!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n💥 Error occurred: {e}")
        print("🔍 Check the logs above for more details")
        raise
