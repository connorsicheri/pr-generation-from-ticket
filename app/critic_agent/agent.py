from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from app.prgen.ai_integration import call_gemini
from .prompt import build_critic_prompt


def run_critic_agent(
    issue_key: str,
    ticket_summary: str,
    ticket_instructions: str,
    changed_files: List[str],
    unified_diff: Optional[str],
    architecture_context: Optional[str] = None,
) -> Dict:
    if os.getenv("ENABLE_CRITIC_AGENT", "true").lower() not in {"1", "true", "yes"}:
        return {
            "risk_level": "low",
            "areas": [],
            "comment": "Critic agent disabled.",
            "suggested_reviewers": [],
        }

    prompt = build_critic_prompt(
        issue_key,
        ticket_summary,
        ticket_instructions,
        changed_files,
        unified_diff,
        architecture_context,
    )
    resp = call_gemini(prompt)
    cleaned = resp.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except Exception as e:
        # fallback
        data = {
            "risk_level": "medium",
            "areas": [],
            "comment": "The critic could not parse a structured response.",
            "suggested_reviewers": [],
        }
    return data


