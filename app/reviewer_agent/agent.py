from __future__ import annotations

import json
from typing import Dict, List

from app.prgen.ai_integration import call_gemini
from .prompt import build_review_prompt


def run_reviewer_agent(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    external_blocks: Dict[str, str] | None,
    repo_snippets: Dict[str, str],
    patches: List[dict],
) -> dict:
    prompt = build_review_prompt(
        issue_key,
        ticket_summary,
        ticket_instructions,
        external_blocks,
        repo_snippets,
        patches,
    )
    response = call_gemini(prompt)
    try:
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            raise ValueError("Reviewer output is not a dict")
        if result.get("outcome") not in {"approve", "request_changes"}:
            raise ValueError("Reviewer outcome missing or invalid")
        return result
    except Exception as e:
        print(f"❌ Reviewer agent returned invalid JSON: {e}")
        print(f"Raw: {response[:500]}...")
        return {
            "outcome": "request_changes",
            "comments": ["Reviewer parsing failed; please inspect changes manually."],
            "suggestions": [],
        }


