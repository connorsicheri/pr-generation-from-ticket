from __future__ import annotations

import json
from typing import Dict, List

from app.prgen.ai_integration import call_gemini
from .prompt import build_update_prompt


def run_updater_agent(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    external_blocks: Dict[str, str] | None,
    repo_snippets: Dict[str, str],
    current_patches: List[dict],
    review: dict,
) -> List[dict]:
    prompt = build_update_prompt(
        issue_key,
        ticket_summary,
        ticket_instructions,
        external_blocks,
        repo_snippets,
        current_patches,
        review,
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
        patches = json.loads(cleaned).get("patches", [])
        if not isinstance(patches, list):
            raise ValueError("Updater output 'patches' is not a list")
        return patches
    except Exception as e:
        print(f"❌ Updater agent returned invalid JSON: {e}")
        print(f"Raw: {response[:500]}...")
        return current_patches


