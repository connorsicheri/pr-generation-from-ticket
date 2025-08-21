from __future__ import annotations

import os
import re
from pathlib import Path
from textwrap import shorten
from typing import Dict, List

from .context_parsing import TicketContext
from .repo_context import gather_candidate_files
from .external_fetchers import (
    fetch_confluence_page,
    fetch_github_pr_context,
    fetch_generic_page,
)
from .ai_integration import (
    call_gemini,
    summarize_text_with_gemini,
    synthesize_summaries_with_gemini,
)
from .prompt_builder import build_prompt


def _gather_external_context(
    ctx: TicketContext,
    gh,
    external_budget_chars: int,
    ticket_summary: str,
    ticket_instructions: str,
) -> Dict[str, str]:
    blocks: Dict[str, str] = {}
    # Confluence
    for idx, url in enumerate(ctx.confluence_urls, start=1):
        try:
            title, text = fetch_confluence_page(url)
            blocks[f"CONFLUENCE[{idx}]: {title}"] = text
        except Exception as e:
            blocks[f"CONFLUENCE[{idx}] ERROR"] = f"Failed to fetch {url}: {e}"
    # GitHub PRs
    if gh is not None:
        for idx, url in enumerate(ctx.github_pr_urls, start=1):
            try:
                pr_sections = fetch_github_pr_context(gh, url)
                for subkey, content in pr_sections.items():
                    blocks[f"GITHUB_PR[{idx}] {subkey}"] = content
            except Exception as e:
                blocks[f"GITHUB_PR[{idx}] ERROR"] = f"Failed to fetch {url}: {e}"
    # Generic
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
        summarized: Dict[str, str] = {}
        for label, text in blocks.items():
            summarized[label] = summarize_text_with_gemini(
                text,
                label,
                char_limit=per_summary_limit,
                ticket_summary=ticket_summary,
                ticket_instructions=ticket_instructions,
            )
        blocks = summarized

    # Trim to budget
    per_block = max(external_budget_chars // len(blocks), 1)
    trimmed = {k: shorten(v, width=per_block, placeholder="\n…\n") for k, v in blocks.items()}
    return trimmed


def _extract_related_links_into_context(ctx: TicketContext, related_urls: List[str]):
    for u in related_urls:
        if u in ctx.confluence_urls or u in ctx.github_pr_urls or u in ctx.github_issue_urls or u in ctx.github_commit_urls or u in ctx.generic_urls:
            continue
        if 'atlassian.net/wiki' in u or '/wiki/spaces/' in u or 'confluence' in u:
            ctx.confluence_urls.append(u)
        elif re.search(r"https://github\.com/[^/]+/[^/]+/pull/\d+", u):
            ctx.github_pr_urls.append(u)
        elif re.search(r"https://github\.com/[^/]+/[^/]+/issues/\d+", u):
            ctx.github_issue_urls.append(u)
        elif re.search(r"https://github\.com/[^/]+/[^/]+/commit/[0-9a-fA-F]{6,40}", u):
            ctx.github_commit_urls.append(u)
        else:
            if not re.search(r"https://github\.com/[^/]+/[^/]+(\.git)?/?$", u):
                ctx.generic_urls.append(u)


def run_prgen_agent(issue, repo_path: Path, gh, related_urls: List[str] | None = None) -> List[dict]:
    """Generate patches implementing the ticket.

    Returns: List[ { path, content } ]
    """
    ctx = TicketContext(issue.fields.description or "")
    if related_urls:
        _extract_related_links_into_context(ctx, related_urls)

    ticket_summary = getattr(issue.fields, 'summary', '') or ''
    ticket_instructions = ctx.instructions

    # Repo snippets for hinted files
    budget_chars = int(os.getenv("MAX_PROMPT_TOKENS", "6000"))
    repo_snippets = gather_candidate_files(repo_path, hinted_paths=ctx.file_paths, budget_chars=budget_chars)

    # External context
    external_budget = int(os.getenv("MAX_EXTERNAL_CONTEXT_CHARS", "20000"))
    external_blocks = _gather_external_context(ctx, gh, external_budget, ticket_summary, ticket_instructions)

    # Optional synthesis
    if os.getenv("ENABLE_CROSS_SOURCE_SYNTHESIS", "true").lower() in {"1", "true", "yes"} and external_blocks:
        synthesis_limit = int(os.getenv("SYNTHESIS_CHAR_LIMIT", "2000"))
        summaries_block = "\n\n".join([f"[{k}]\n{v}" for k, v in external_blocks.items()])
        synthesis = synthesize_summaries_with_gemini(summaries_block, ticket_summary, ticket_instructions, char_limit=synthesis_limit)
        external_blocks = {"SYNTHESIS": synthesis, **external_blocks}

    # Prompt and model call
    prompt = build_prompt(issue, ctx, repo_snippets, external_blocks)
    json_text = call_gemini(prompt)

    # Parse patches
    import json as _json
    cleaned = json_text.strip()
    if cleaned.startswith('```json'):
        cleaned = cleaned[7:]
    elif cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    patches = _json.loads(cleaned).get("patches", [])
    return patches


