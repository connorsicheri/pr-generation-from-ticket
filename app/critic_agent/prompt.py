from __future__ import annotations

from typing import List, Optional


def build_critic_prompt(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    changed_files: List[str],
    unified_diff: Optional[str],
    architecture_context: Optional[str] = None,
) -> str:
    parts: List[str] = []
    parts.append(
        f"You are a senior staff engineer and gatekeeper for risky changes. "
        f"Analyze the proposed changes for Jira ticket {issue_key} and explain risks in plain English."
    )
    parts.append(f"Ticket summary: {ticket_summary}")
    parts.append("Ticket instructions:\n" + (ticket_instructions or ""))
    if architecture_context:
        parts.append("Architecture context (read-only):\n" + architecture_context)
    parts.append("Changed files:\n" + "\n".join(f" - {p}" for p in changed_files))
    if unified_diff:
        # Keep the diff short if huge; LLM token budget managed outside if needed
        parts.append("Unified diff (context):\n" + unified_diff)

    parts.append(
        "Return ONLY valid JSON with keys: \n"
        "{\n"
        "  \"risk_level\": one of [\"low\", \"medium\", \"high\"],\n"
        "  \"areas\": [short strings of impacted architecture components],\n"
        "  \"comment\": plain-English multi-paragraph PR comment for humans,\n"
        "  \"suggested_reviewers\": [github usernames without @ if obvious]\n"
        "}\n"
        "No markdown code fences, no extra commentary."
    )
    return "\n\n".join(parts)


