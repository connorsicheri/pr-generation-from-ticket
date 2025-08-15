from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import List

from .jira_client import get_jira_client, fetch_issue, get_related_links
from .github_utils import get_github_client, create_pull_request
from .git_utils import clone_and_branch, commit_push
from .context_parsing import TicketContext
from .repo_context import gather_candidate_files
from .external_fetchers import fetch_confluence_page, fetch_github_pr_context, fetch_generic_page
from .ai_integration import call_gemini, summarize_text_with_gemini, synthesize_summaries_with_gemini
from .prompt_builder import build_prompt


def extract_repo_url(issue) -> str:
    # Try description for GitHub URL
    description = issue.fields.description or ""
    if description:
        github_urls = re.findall(r'https://github\.com/[^\s]+', description)
        if github_urls:
            return github_urls[0].rstrip('.,;)')
        git_urls = re.findall(r'[^\s]*\.git[^\s]*', description)
        if git_urls:
            return git_urls[0].rstrip('.,;)')

    possible_repo_fields = [
        'customfield_11712',
        'customfield_12345', 'customfield_10001', 'customfield_10002', 'customfield_10003'
    ]
    for field_name in possible_repo_fields:
        try:
            field_value = getattr(issue.fields, field_name, None)
            if field_value and ('github.com' in str(field_value) or '.git' in str(field_value)):
                return str(field_value)
        except Exception:
            continue
    raise ValueError("Repository URL must be specified in ticket description or custom field.")


def gather_external_context(ctx: TicketContext, gh, external_budget_chars: int, ticket_summary: str, ticket_instructions: str):
    blocks = {}
    for idx, url in enumerate(ctx.confluence_urls, start=1):
        try:
            title, text = fetch_confluence_page(url)
            blocks[f"CONFLUENCE[{idx}]: {title}"] = text
        except Exception as e:
            blocks[f"CONFLUENCE[{idx}] ERROR"] = f"Failed to fetch {url}: {e}"
    if gh is not None:
        for idx, url in enumerate(ctx.github_pr_urls, start=1):
            try:
                pr_sections = fetch_github_pr_context(gh, url)
                for subkey, content in pr_sections.items():
                    blocks[f"GITHUB_PR[{idx}] {subkey}"] = content
            except Exception as e:
                blocks[f"GITHUB_PR[{idx}] ERROR"] = f"Failed to fetch {url}: {e}"
    # Generic pages
    for idx, url in enumerate(ctx.generic_urls, start=1):
        try:
            title, text = fetch_generic_page(url)
            blocks[f"WEB[{idx}]: {title}"] = text
        except Exception as e:
            blocks[f"WEB[{idx}] ERROR"] = f"Failed to fetch {url}: {e}"

    if not blocks:
        return blocks

    enable_summarization = os.getenv("SUMMARIZE_EXTERNAL_CONTEXT", "true").lower() in {"1", "true", "yes"}
    configured_per_source_cap = int(os.getenv("PER_SOURCE_SUMMARY_CHAR_LIMIT", "3000"))
    per_summary_limit = min(
        max(external_budget_chars // max(len(blocks), 1), 500),
        configured_per_source_cap,
    )
    if enable_summarization:
        summarized = {}
        for label, text in blocks.items():
            summarized[label] = summarize_text_with_gemini(
                text,
                label,
                char_limit=per_summary_limit,
                ticket_summary=ticket_summary,
                ticket_instructions=ticket_instructions,
            )
        blocks = summarized

    # Final trim to budget
    from textwrap import shorten
    per_block = max(external_budget_chars // len(blocks), 1)
    trimmed = {k: shorten(v, width=per_block, placeholder="\n…\n") for k, v in blocks.items()}
    return trimmed


def generate_changes_with_ai(issue, repo_path: Path, gh) -> List[dict]:
    ctx = TicketContext(issue.fields.description or "")
    # Merge related links from Jira remote links into the context
    try:
        jira = get_jira_client()
        related_urls = get_related_links(jira, issue)
    except Exception:
        related_urls = []
    # Feed related urls back into classification (simple append to generic for now)
    for u in related_urls:
        if u not in ctx.confluence_urls and u not in ctx.github_pr_urls and u not in ctx.github_issue_urls and u not in ctx.github_commit_urls and u not in ctx.generic_urls:
            # naive classification
            if 'atlassian.net/wiki' in u or '/wiki/spaces/' in u or 'confluence' in u:
                ctx.confluence_urls.append(u)
            elif re.search(r"https://github\.com/[^/]+/[^/]+/pull/\d+", u):
                ctx.github_pr_urls.append(u)
            elif re.search(r"https://github\.com/[^/]+/[^/]+/issues/\d+", u):
                ctx.github_issue_urls.append(u)
            elif re.search(r"https://github\.com/[^/]+/[^/]+/commit/[0-9a-fA-F]{6,40}", u):
                ctx.github_commit_urls.append(u)
            else:
                ctx.generic_urls.append(u)
    budget_chars = int(os.getenv("MAX_PROMPT_TOKENS", "6000"))
    repo_snippets = gather_candidate_files(repo_path, hinted_paths=ctx.file_paths, budget_chars=budget_chars)
    external_budget = int(os.getenv("MAX_EXTERNAL_CONTEXT_CHARS", "20000"))
    ticket_summary = getattr(issue.fields, 'summary', '') or ''
    ticket_instructions = ctx.instructions
    external_blocks = gather_external_context(ctx, gh, external_budget, ticket_summary, ticket_instructions)

    # Optional cross-source synthesis block
    if os.getenv("ENABLE_CROSS_SOURCE_SYNTHESIS", "true").lower() in {"1", "true", "yes"} and external_blocks:
        synthesis_limit = int(os.getenv("SYNTHESIS_CHAR_LIMIT", "2000"))
        # Build summaries block
        summaries_block = "\n\n".join([f"[{k}]\n{v}" for k, v in external_blocks.items()])
        synthesis = synthesize_summaries_with_gemini(summaries_block, ticket_summary, ticket_instructions, char_limit=synthesis_limit)
        external_blocks = {"SYNTHESIS": synthesis, **external_blocks}
    prompt = build_prompt(issue, ctx, repo_snippets, external_blocks)
    json_text = call_gemini(prompt)
    # Log a compact preview of the model output
    try:
        preview_n = int(os.getenv("LOG_MODEL_OUTPUT_PREVIEW_CHARS", "600"))
        if preview_n > 0:
            print(f"📤 Model output preview ({len(json_text)} chars):\n{json_text[:preview_n]}{'…' if len(json_text) > preview_n else ''}")
    except Exception:
        pass
    import json
    try:
        cleaned_text = json_text.strip()
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]
        elif cleaned_text.startswith('```'):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        patches = json.loads(cleaned_text).get("patches", [])
        print(f"✅ Parsed {len(patches)} file patch(es)")
        return patches
    except Exception as e:
        print(f"❌ Failed to parse AI response: {e}")
        print(f"Raw response: {json_text[:300]}...")
        print(f"Cleaned response: {cleaned_text[:300] if 'cleaned_text' in locals() else 'N/A'}...")
        raise ValueError("Malformed JSON from Gemini") from e


def apply_patches(changes: List[dict], repo_path: Path):
    print(f"💾 Writing {len(changes)} file(s)...")
    for fc in changes:
        file_path = fc["path"]
        content = fc["content"]
        dst = repo_path / file_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        print(f"   ✅ {file_path}")
    print(f"✅ Applied all patches")


def run_pipeline(issue_key: str):
    print("📄 STEP 1: Fetching Jira ticket")
    print("-" * 30)
    jira = get_jira_client()
    issue = fetch_issue(jira, issue_key)

    print("\n📄 STEP 2: Extracting repository information")
    print("-" * 30)
    repo_url = extract_repo_url(issue)
    print(f"📁 Repository URL: {repo_url}")
    desired_branch = f"ai/{issue.key.lower()}"
    base_branch = os.getenv("DEFAULT_BASE_BRANCH", "main")
    print(f"🌿 New branch: {desired_branch}")
    print(f"🌿 Base branch: {base_branch}")

    print("\n📄 STEP 3: Connecting to GitHub")
    print("-" * 30)
    gh = get_github_client()
    print("✅ GitHub client initialized")

    print("\n📄 STEP 4: Processing changes")
    print("-" * 30)
    with tempfile.TemporaryDirectory(prefix="ai_pr_") as tmp:
        print(f"📁 Using temporary directory: {tmp}")
        repo_path, branch_name = clone_and_branch(repo_url, desired_branch, Path(tmp))

        print("\n🤖 Generating AI changes...")
        patches = generate_changes_with_ai(issue, repo_path, gh)

        print()
        apply_patches(patches, repo_path)
        print()
        commit_message = f"{issue.key}: {issue.fields.summary}"
        commit_push(repo_path, branch_name, commit_message)

        print("\n📄 STEP 5: Creating pull request")
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

    print("🎉 SUCCESS!")
    print("=" * 50)
    print(f"✅ Pull request created: #{pr.number}")
    print(f"🔗 URL: {pr.html_url}")
    print(f"🌿 Branch: {branch_name}")
    print(f"🎫 Ticket: {issue_key}")
    print()
    print("👍 Your AI-generated pull request is ready for review!")

