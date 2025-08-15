from __future__ import annotations

from typing import Dict

from .context_parsing import TicketContext


def build_prompt(issue, ctx: TicketContext, repo_snippets: Dict[str, str], external_blocks: Dict[str, str] | None = None) -> str:
    prompt = (
        f"You are a senior software engineer tasked with implementing Jira ticket {issue.key}.\n\n"
        f"Ticket summary: {issue.fields.summary}\n\n"
        "Ticket description (user instructions):\n" + ctx.instructions + "\n\n"
        "Repository snippets (read‑only context):\n"
    )
    for path, content in repo_snippets.items():
        prompt += f"--- BEGIN FILE {path} ---\n{content}\n--- END FILE {path} ---\n"
    if external_blocks:
        prompt += "\nExternal references (read‑only context):\n"
        for label, content in external_blocks.items():
            prompt += f"--- BEGIN {label} ---\n{content}\n--- END {label} ---\n"
    # Log a compact preview of what we are sending to the model
    try:
        from os import getenv
        preview_n = int(getenv("LOG_PROMPT_PREVIEW_CHARS", "800"))
        if preview_n > 0:
            preview = (prompt[:preview_n] + ("…" if len(prompt) > preview_n else ""))
            print(f"🧾 Prompt preview ({len(prompt)} chars total):\n{preview}")
    except Exception:
        pass
    prompt += (
        "\nReturn ONLY valid JSON shaped as:\n"
        "{ \"patches\": [ { \"path\": \"relative/file\", \"content\": \"new content…\" }, … ] }\n"
        "No markdown fences, no commentary."
    )
    return prompt

