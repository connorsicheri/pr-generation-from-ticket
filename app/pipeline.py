from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import List

from app.prgen.jira_client import get_jira_client, fetch_issue
from app.prgen.github_utils import (
    get_github_client,
    find_open_pr,
    post_pr_comment,
    build_iteration_summary_comment,
    read_latest_ai_state_from_comments,
)
from app.prgen.git_utils import clone_and_branch, commit_push
from app.prgen.git_utils import get_unified_diff
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
    print("\n" + "=" * 70)
    print("🔭 Reviewer ↔ Updater Refinement")
    print("=" * 70)
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

    max_iters = int(os.getenv("REVIEW_LOOP_MAX_ITERS", "5"))
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

        # Context overview
        base_branch_preview = os.getenv("DEFAULT_BASE_BRANCH", "main")
        print("\n" + "-" * 70)
        print("📋 Context")
        print("-" * 70)
        print(f"🎫 Ticket: {issue.key} — {ticket_summary}")
        print(f"🌿 PR branch: {pr_branch}")
        print(f"🔧 Base branch: {base_branch_preview}")
        print(f"🗂️  Candidate files: {len(repo_snippets)}")
        if external_blocks:
            print(f"🌐 External context blocks: {len(external_blocks)}")
        print("-" * 70)

        # Try to find the PR to attach comments/state to
        pr = find_open_pr(repo, desired_branch, expected_title=getattr(issue.fields, 'summary', None))
        # Load previous loop state if present to resume
        previous_state = read_latest_ai_state_from_comments(pr) if pr else None
        start_iteration = 1
        current_patches: List[dict] = []
        if isinstance(previous_state, dict):
            try:
                start_iteration = int(previous_state.get("next_iteration", 1))
            except Exception:
                start_iteration = 1
            if isinstance(previous_state.get("current_patches"), list):
                current_patches = previous_state.get("current_patches")

        def _is_trivial_comment(text: str) -> bool:
            t = (text or "").lower()
            trivial_markers = [
                "nit", "minor", "typo", "spelling", "whitespace", "format", "style",
                "rename variable", "naming", "docstring", "comment only", "import order",
                "lint", "trailing space", "indent", "prettier",
            ]
            return any(m in t for m in trivial_markers) and not any(k in t for k in ["bug", "security", "logic", "breaks", "failing", "error"])

        for iteration in range(start_iteration, max_iters + 1):
            print("\n" + "-" * 70)
            print(f"🔁 Iteration {iteration}/{max_iters}")
            print("-" * 70)
            # Compute a unified diff against the base branch for the reviewer
            base_branch = os.getenv("DEFAULT_BASE_BRANCH", "main")
            try:
                unified_diff = get_unified_diff(repo_path, base_branch, pr_branch)
            except Exception as e:
                print(f"ℹ️  Could not compute diff: {e}")
                unified_diff = None
            review = run_reviewer_agent(
                issue.key,
                ticket_summary,
                ticket_instructions,
                external_blocks,
                repo_snippets,
                current_patches,
                unified_diff,
            )
            outcome = review.get('outcome')
            comments = review.get('comments') or []
            suggestions = review.get('suggestions') or []
            print(f"🧪 Reviewer outcome: {outcome} | comments: {len(comments)} | suggestions: {len(suggestions)}")
            for c in comments[:5]:
                print(f"   💬 {c}")
            # Adaptive stopping: auto-approve if only n trivial comments remain
            trivial_threshold = int(os.getenv("REVIEW_TRIVIAL_THRESHOLD", "0"))
            trivial_count = sum(1 for c in comments if _is_trivial_comment(c))
            all_trivial = (len(comments) > 0 and trivial_count == len(comments)) or (len(comments) == 0)
            auto_approved = False
            changed_paths_for_comment: List[str] = []
            if outcome == 'approve' or (trivial_threshold > 0 and len(comments) <= trivial_threshold and all_trivial):
                auto_approved = (outcome != 'approve')
                # Post iteration summary comment before exiting
                if pr:
                    state = {
                        "iteration": iteration,
                        "outcome": "approve",
                        "auto_approved": auto_approved,
                        "comments_count": len(comments),
                        "suggestions_count": len(suggestions),
                        "changed_files": changed_paths_for_comment,
                        "current_patches": current_patches,
                        "next_iteration": iteration + 1,
                        "branch": pr_branch,
                    }
                    body = build_iteration_summary_comment(
                        iteration=iteration,
                        outcome="approve",
                        comments_count=len(comments),
                        suggestions_count=len(suggestions),
                        changed_files=changed_paths_for_comment,
                        branch=pr_branch,
                        auto_approved=auto_approved,
                        state=state,
                    )
                    post_pr_comment(pr, body)
                print("✅ Approved by reviewer — exiting loop.")
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
                print("ℹ️  Updater did not produce patches — stopping loop.")
                # Still post a summary comment to record the state
                if pr:
                    state = {
                        "iteration": iteration,
                        "outcome": outcome or "request_changes",
                        "auto_approved": False,
                        "comments_count": len(comments),
                        "suggestions_count": len(suggestions),
                        "changed_files": [],
                        "current_patches": current_patches,
                        "next_iteration": iteration + 1,
                        "branch": pr_branch,
                    }
                    body = build_iteration_summary_comment(
                        iteration=iteration,
                        outcome=outcome or "request_changes",
                        comments_count=len(comments),
                        suggestions_count=len(suggestions),
                        changed_files=[],
                        branch=pr_branch,
                        auto_approved=False,
                        state=state,
                    )
                    post_pr_comment(pr, body)
                break
            apply_patches(new_patches, repo_path)
            try:
                changed_paths_for_comment = [p.get('path') for p in new_patches if isinstance(p, dict)]
                if changed_paths_for_comment:
                    print(f"📝 Files updated ({len(changed_paths_for_comment)}):")
                    for p in changed_paths_for_comment[:10]:
                        print(f"   • {p}")
                    if len(changed_paths_for_comment) > 10:
                        print(f"   • … and {len(changed_paths_for_comment) - 10} more")
            except Exception:
                pass
            commit_message = f"{issue.key}: reviewer updates"
            try:
                commit_push(repo_path, pr_branch, commit_message)
            except SystemExit:
                print("ℹ️  No changes to commit in this iteration")
                # Post comment even if nothing to commit
                if pr:
                    state = {
                        "iteration": iteration,
                        "outcome": outcome or "request_changes",
                        "auto_approved": False,
                        "comments_count": len(comments),
                        "suggestions_count": len(suggestions),
                        "changed_files": changed_paths_for_comment,
                        "current_patches": current_patches,
                        "next_iteration": iteration + 1,
                        "branch": pr_branch,
                    }
                    body = build_iteration_summary_comment(
                        iteration=iteration,
                        outcome=outcome or "request_changes",
                        comments_count=len(comments),
                        suggestions_count=len(suggestions),
                        changed_files=changed_paths_for_comment,
                        branch=pr_branch,
                        auto_approved=False,
                        state=state,
                    )
                    post_pr_comment(pr, body)
                break
            current_patches = new_patches
            # Post per-iteration summary with state persistence
            if pr:
                state = {
                    "iteration": iteration,
                    "outcome": outcome or "request_changes",
                    "auto_approved": False,
                    "comments_count": len(comments),
                    "suggestions_count": len(suggestions),
                    "changed_files": changed_paths_for_comment,
                    "current_patches": current_patches,
                    "next_iteration": iteration + 1,
                    "branch": pr_branch,
                }
                body = build_iteration_summary_comment(
                    iteration=iteration,
                    outcome=outcome or "request_changes",
                    comments_count=len(comments),
                    suggestions_count=len(suggestions),
                    changed_files=changed_paths_for_comment,
                    branch=pr_branch,
                    auto_approved=False,
                    state=state,
                )
                post_pr_comment(pr, body)
    print("\n" + "=" * 70)
    print("✅ Review loop finished")
    print("=" * 70)


