from __future__ import annotations

from typing import Dict, List


def build_review_prompt(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    external_blocks: Dict[str, str] | None,
    repo_snippets: Dict[str, str],
    patches: List[dict],
    unified_diff: str | None = None,
) -> str:
    prompt = (
        f"You are a senior code reviewer assessing changes for Jira ticket {issue_key}.\n\n"
        f"Ticket summary:\n{ticket_summary}\n\n"
        f"Ticket instructions:\n{ticket_instructions}\n\n"
    )
    if external_blocks:
        prompt += "Relevant external context:\n"
        for label, content in external_blocks.items():
            prompt += f"--- {label} ---\n{content}\n\n"
    prompt += "Repository context (pre-change snippets):\n"
    for path, content in repo_snippets.items():
        prompt += f"--- FILE {path} ---\n{content}\n\n"
    prompt += "Proposed changes (patches overview):\n"
    for p in patches:
        prompt += f"- {p.get('path')}: ({len(p.get('content',''))} chars)\n"
    if unified_diff:
        # Trim very large diffs to avoid token blow-ups
        max_diff_chars = 20000
        diff_text = unified_diff if len(unified_diff) <= max_diff_chars else (unified_diff[:max_diff_chars] + "\n… (truncated)\n")
        prompt += "\nUnified diff (base vs head):\n"
        prompt += f"""\n--- BEGIN DIFF ---\n{diff_text}\n--- END DIFF ---\n"""
    prompt += (
        "\nTask:\n"
        "1) Verify the patches implement the ticket instructions and align with external context.\n"
        "2) Review the unified diff to validate correctness, safety, and completeness.\n"
        "3) Identify issues: missing logic, incorrect assumptions, formatting, naming, tests/docs gaps.\n"
        "4) Provide actionable review comments.\n"
        "5) Decide outcome: 'approve' or 'request_changes'.\n\n"
        "Return ONLY valid JSON shaped as:\n"
        "{\n  \"outcome\": \"approve|request_changes\",\n  \"comments\": [\"...\"],\n  \"suggestions\": [\n    { \"path\": \"relative/file\", \"instructions\": \"what to change\" }\n  ]\n}\n"
    )
    return prompt


