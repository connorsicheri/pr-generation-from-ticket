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
    
    repo_path = workdir / "repo"
    
    # For HTTPS URLs, we'll use the GitHub token for authentication
    if repo_url.startswith('https://github.com/'):
        # GitHub requires token authentication for private repos
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            # Insert token into URL for authentication
            auth_url = repo_url.replace('https://github.com/', f'https://{github_token}@github.com/')
            print(f"   🔐 Using GitHub token for authentication")
            run(["git", "clone", auth_url, str(repo_path)])
        else:
            print(f"   ⚠️  No GitHub token found, trying without authentication")
            run(["git", "clone", repo_url, str(repo_path)])
    else:
        # SSH or other URLs - use as-is (assumes SSH keys are configured)
        if repo_url.startswith('git@'):
            print(f"   🔑 Using SSH authentication")
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
        self.file_paths, self.instructions = self._parse(self.description)
        print(f"📁 Found {len(self.file_paths)} file(s): {self.file_paths}")

    @staticmethod
    def _parse(text: str) -> Tuple[List[str], str]:
        # Jira uses {{...}} for code blocks, not backticks
        # Matches: {{path/to/file.ext}} with nested directories
        file_regex = re.compile(r"\{\{([^{}\n]*[/\\]?[^{}\n/\\]*\.(?:py|go|js|ts|tsx|java|yaml|json|yml|md|txt|sh|jsx|vue|php|rb|cpp|c|h))\}\}")
        paths = file_regex.findall(text)
        
        # Also support backticks as fallback for manual entry
        backtick_regex = re.compile(r"`([^`\n]*[/\\]?[^`\n/\\]*\.(?:py|go|js|ts|tsx|java|yaml|json|yml|md|txt|sh|jsx|vue|php|rb|cpp|c|h))`")
        backtick_paths = backtick_regex.findall(text)
        
        # Combine both patterns
        all_paths = paths + backtick_paths
        
        # Clean up paths - remove leading ./ and normalize
        cleaned_paths = []
        for path in all_paths:
            cleaned_path = path.strip()
            # Remove leading ./
            if cleaned_path.startswith('./'):
                cleaned_path = cleaned_path[2:]
            # Convert backslashes to forward slashes for consistency
            cleaned_path = cleaned_path.replace('\\', '/')
            cleaned_paths.append(cleaned_path)
        
        # Remove both patterns from instructions
        instructions = re.sub(file_regex, "", text)
        instructions = re.sub(backtick_regex, "", instructions).strip()
        return cleaned_paths, instructions


# Token helper (roughly 4 chars per token when tiktoken unavailable)
_encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(txt: str) -> int:  # kept for potential future limits
    return len(_encoding.encode(txt))


def gather_candidate_files(repo_path: Path, hinted_paths: List[str], budget_chars: int = 6000) -> Dict[str, str]:
    """Return *only* the files explicitly referenced in the ticket.

    Each file is truncated to fit within `budget_chars` in total. No automatic
    discovery of additional repository context is performed.
    """
    print(f"📂 Loading {len(hinted_paths)} file(s) from repository...")
    
    selected: Dict[str, str] = {}
    per_file_budget = max(budget_chars // max(len(hinted_paths), 1), 1)

    for rel in hinted_paths:
        p = repo_path / rel
        if not p.exists():
            print(f"   ⚠️  {rel} (will be created)")
            continue
        content = p.read_text("utf-8", errors="ignore")
        truncated_content = shorten(content, width=per_file_budget, placeholder="\n…\n")
        selected[rel] = truncated_content
        print(f"   ✅ {rel}")
    
    return selected


# ---------------------------------------------------------------------------
# Gemini API integration
# ---------------------------------------------------------------------------

def call_gemini(prompt: str) -> str:
    print(f"🤖 Generating code with {os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')}...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var missing.")
    
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    response = model.generate_content(prompt)
    result = response.text.strip()
    
    print(f"   ✅ Generated {len(result)} characters of code")
    return result


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
        # Clean up the response - remove markdown code fences if present
        cleaned_text = json_text.strip()
        
        # Remove ```json at the start and ``` at the end
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]  # Remove ```json
        elif cleaned_text.startswith('```'):
            cleaned_text = cleaned_text[3:]   # Remove ```
            
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]  # Remove trailing ```
            
        cleaned_text = cleaned_text.strip()
        
        # Parse the cleaned JSON
        data = json.loads(cleaned_text)
        patches = data.get("patches", [])
        print(f"✅ Parsed {len(patches)} file patch(es)")
        return patches
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse AI response: {e}")
        print(f"Raw response: {json_text[:300]}...")
        print(f"Cleaned response: {cleaned_text[:300] if 'cleaned_text' in locals() else 'N/A'}...")
        raise ValueError("Malformed JSON from Gemini") from e


def generate_changes_with_ai(issue, repo_path: Path) -> List[dict]:
    # Parse ticket context
    ctx = TicketContext(issue.fields.description or "")
    
    # Gather file context
    budget_chars = int(os.getenv("MAX_PROMPT_TOKENS", "6000"))
    repo_snippets = gather_candidate_files(
        repo_path,
        hinted_paths=ctx.file_paths,
        budget_chars=budget_chars,
    )
    
    # Build and send prompt
    prompt = build_prompt(issue, ctx, repo_snippets)
    json_text = call_gemini(prompt)
    
    # Parse response
    patches = parse_json_patches(json_text)
    
    return patches


def apply_patches(changes: List[dict], repo_path: Path):
    print(f"💾 Writing {len(changes)} file(s)...")
    for fc in changes:
        file_path = fc["path"]
        content = fc["content"]
        dst = repo_path / file_path
        
        # Create directory if it doesn't exist
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        dst.write_text(content, encoding="utf-8")
        print(f"   ✅ {file_path}")
    
    print(f"✅ Applied all patches")


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
    
    repo_url = None
    
    # First, try to extract from ticket description
    description = issue.fields.description or ""
    if description:
        import re
        # Look for GitHub URLs in description
        github_urls = re.findall(r'https://github\.com/[^\s]+', description)
        if github_urls:
            repo_url = github_urls[0].rstrip('.,;)')  # Clean up common trailing chars
            print(f"📁 Found repository URL in description: {repo_url}")
        else:
            # Look for any git URLs
            git_urls = re.findall(r'[^\s]*\.git[^\s]*', description)
            if git_urls:
                repo_url = git_urls[0].rstrip('.,;)')
                print(f"📁 Found git URL in description: {repo_url}")
    
    # If not found in description, check custom fields
    if not repo_url:
        # Based on your test output, check the actual custom fields from your Jira
        possible_repo_fields = [
            'customfield_11712',  # This had a URL in your test data
            'customfield_12345', 'customfield_10001', 'customfield_10002', 'customfield_10003'
        ]
        
        for field_name in possible_repo_fields:
            try:
                field_value = getattr(issue.fields, field_name, None)
                if field_value and ('github.com' in str(field_value) or '.git' in str(field_value)):
                    repo_url = str(field_value)
                    print(f"📁 Found repository URL in {field_name}: {repo_url}")
                    break
            except:
                continue
    
    # If no repo URL found anywhere, fail with helpful message
    if not repo_url:
        print("❌ Error: No repository URL found!")
        print("💡 Solutions:")
        print("   1. Add GitHub URL to ticket description")
        print("   2. Configure a custom field in Jira with repository URL")
        print("   3. Example description: 'Fix bug in https://github.com/yourorg/yourrepo.git'")
        raise ValueError("Repository URL must be specified in ticket description or custom field.")
    
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
