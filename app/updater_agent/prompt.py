from __future__ import annotations

from typing import Dict, List


def build_update_prompt(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    external_blocks: Dict[str, str] | None,
    repo_snippets: Dict[str, str],
    current_patches: List[dict],
    review: dict,
) -> str:
    prompt = (
        f"You are an implementation agent updating patches for Jira ticket {issue_key}.\n\n"
        f"Ticket summary:\n{ticket_summary}\n\n"
        f"Ticket instructions:\n{ticket_instructions}\n\n"
    )
    if external_blocks:
        prompt += "Relevant external context:\n"
        for label, content in external_blocks.items():
            prompt += f"--- {label} ---\n{content}\n\n"
    prompt += "Current proposed patches:\n"
    for p in current_patches:
        prompt += f"- {p.get('path')}: ({len(p.get('content',''))} chars)\n"
    prompt += "\nReviewer feedback:\n"
    outcome = review.get("outcome")
    comments = review.get("comments") or []
    suggestions = review.get("suggestions") or []
    prompt += f"Outcome: {outcome}\n"
    if comments:
        prompt += "Comments:\n" + "\n".join([f"- {c}" for c in comments[:10]]) + "\n"
    if suggestions:
        prompt += "Suggestions:\n" + "\n".join([f"- {s.get('path')}: {s.get('instructions')}" for s in suggestions]) + "\n"
    prompt += (
        "\nTask:\n"
        "Update the patches to address the reviewer feedback and fully implement the ticket.\n"
        "Maintain existing functionality unless the ticket specifies changes.\n"
        "Return ONLY valid JSON with shape: { \"patches\": [ { \"path\": \"relative/file\", \"content\": \"full file content\" } ] }\n"
    )
    return prompt


