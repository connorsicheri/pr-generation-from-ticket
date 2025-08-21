from __future__ import annotations

import os


REQUIRED_ENVS = [
    "JIRA_URL",
    "JIRA_EMAIL",
    "JIRA_TOKEN",
    "GITHUB_TOKEN",
    "GEMINI_API_KEY",
]


def check_env() -> dict:
    missing = [k for k in REQUIRED_ENVS if not os.environ.get(k)]
    optional = {
        "DEFAULT_BASE_BRANCH": os.environ.get("DEFAULT_BASE_BRANCH", "main"),
        "MAX_PROMPT_TOKENS": os.environ.get("MAX_PROMPT_TOKENS", "6000"),
    }
    return {"missing": missing, "optional": optional}


def is_healthy() -> bool:
    return len(check_env()["missing"]) == 0


