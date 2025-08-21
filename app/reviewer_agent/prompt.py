from __future__ import annotations

from typing import Dict, List


def build_review_prompt(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    external_blocks: Dict[str, str] | None,
    repo_snippets: Dict[str, str],
    patches: List[dict],
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
    prompt += "Proposed changes (patches):\n"
    for p in patches:
        prompt += f"- {p.get('path')}: ({len(p.get('content',''))} chars)\n"
    prompt += (
        "\nTask:\n"
        "1) Verify the patches implement the ticket instructions and align with external context.\n"
        "2) Identify issues: missing logic, incorrect assumptions, formatting, naming, tests/docs gaps.\n"
        "3) Provide actionable review comments.\n"
        "4) Decide outcome: 'approve' or 'request_changes'.\n\n"
        "Return ONLY valid JSON shaped as:\n"
        "{\n  \"outcome\": \"approve|request_changes\",\n  \"comments\": [\"...\"],\n  \"suggestions\": [\n    { \"path\": \"relative/file\", \"instructions\": \"what to change\" }\n  ]\n}\n"
    )
    return prompt


