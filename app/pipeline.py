from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import List

from app.prgen.jira_client import get_jira_client, fetch_issue
from app.prgen.github_utils import get_github_client
from app.prgen.git_utils import clone_and_branch, commit_push
from app.prgen.pipeline import apply_patches, extract_repo_url
from app.reviewer_agent.agent import run_reviewer_agent
from app.updater_agent.agent import run_updater_agent
from app.prgen.context_parsing import TicketContext
from app.prgen.repo_context import gather_candidate_files
from app.prgen.pipeline import gather_external_context
from app.prgen.pipeline import run_pipeline as run_prgen_pipeline


def run_pipeline(issue_key: str):
    # 1) Run the PRGen pipeline end-to-end (initial PR creation)
    run_prgen_pipeline(issue_key)

    # 2) Start the Reviewer↔Updater loop to refine the PR
    print("\n🔭 Entering Reviewer↔Updater loop")
    jira = get_jira_client()
    issue = fetch_issue(jira, issue_key)
    gh = get_github_client()
    repo_url = extract_repo_url(issue)
    parts = repo_url.rstrip(".git").split("/")[-2:]
    repo_full_name = "/".join(parts)
    repo = gh.get_repo(repo_full_name)
    desired_branch = f"ai/{issue.key.lower()}"
    pr_branch = desired_branch
    for pr in repo.get_pulls(state="open"):
        try:
            if pr.title == issue.fields.summary and pr.head and pr.head.ref.startswith(desired_branch):
                pr_branch = pr.head.ref
                break
        except Exception:
            continue

    max_iters = int(os.getenv("REVIEW_LOOP_MAX_ITERS", "2"))
    if os.getenv("ENABLE_REVIEW_LOOP", "true").lower() not in {"1", "true", "yes"}:
        print("ℹ️  Review loop disabled")
        return

    with tempfile.TemporaryDirectory(prefix="ai_pr_review_") as tmp:
        print(f"📁 Using temporary directory for review loop: {tmp}")
        repo_path, _ = clone_and_branch(repo_url, pr_branch, Path(tmp))

        ctx = TicketContext(issue.fields.description or "")
        budget_chars = int(os.getenv("MAX_PROMPT_TOKENS", "6000"))
        repo_snippets = gather_candidate_files(repo_path, hinted_paths=ctx.file_paths, budget_chars=budget_chars)
        external_budget = int(os.getenv("MAX_EXTERNAL_CONTEXT_CHARS", "20000"))
        ticket_summary = getattr(issue.fields, 'summary', '') or ''
        ticket_instructions = ctx.instructions
        external_blocks = gather_external_context(ctx, gh, external_budget, ticket_summary, ticket_instructions)

        current_patches: List[dict] = []
        for iteration in range(1, max_iters + 1):
            print(f"🔁 Review iteration {iteration}/{max_iters}")
            review = run_reviewer_agent(
                issue.key,
                ticket_summary,
                ticket_instructions,
                external_blocks,
                repo_snippets,
                current_patches,
            )
            print(f"🧪 Reviewer outcome: {review.get('outcome')}")
            for c in (review.get('comments') or [])[:5]:
                print(f"   💬 {c}")
            if review.get('outcome') == 'approve':
                break
            new_patches = run_updater_agent(
                issue.key,
                ticket_summary,
                ticket_instructions,
                external_blocks,
                repo_snippets,
                current_patches,
                review,
            )
            if not new_patches:
                print("ℹ️  Updater did not produce patches; stopping loop.")
                break
            apply_patches(new_patches, repo_path)
            commit_message = f"{issue.key}: reviewer updates"
            try:
                commit_push(repo_path, pr_branch, commit_message)
            except SystemExit:
                print("ℹ️  No changes to commit in this iteration")
                break
            current_patches = new_patches
    print("✅ Review loop finished")


