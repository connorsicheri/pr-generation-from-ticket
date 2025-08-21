from __future__ import annotations

import os

from app.health import check_env, is_healthy


def test_health_reports_missing_envs(monkeypatch):
    for k in ["JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "GITHUB_TOKEN", "GEMINI_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    result = check_env()
    for k in ["JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "GITHUB_TOKEN", "GEMINI_API_KEY"]:
        assert k in result["missing"]
    assert is_healthy() is False


def test_health_succeeds_with_envs(monkeypatch):
    monkeypatch.setenv("JIRA_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
    monkeypatch.setenv("JIRA_TOKEN", "token")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_token")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini")
    result = check_env()
    assert result["missing"] == []
    assert is_healthy() is True


