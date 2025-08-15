from __future__ import annotations

import os
from jira import JIRA


def get_jira_client() -> JIRA:
    print("🔗 Connecting to Jira...")
    jira_url = os.environ["JIRA_URL"]
    jira_email = os.environ["JIRA_EMAIL"]
    jira_token = os.environ["JIRA_TOKEN"]
    print(f"   Server: {jira_url}")
    print(f"   Email: {jira_email}")
    print(f"   Token: {jira_token[:10]}...{jira_token[-4:]} (masked)")
    print("   Using basic authentication (email + token)...")
    return JIRA(server=jira_url, basic_auth=(jira_email, jira_token))


def fetch_issue(jira: JIRA, issue_key: str):
    print(f"📋 Fetching Jira issue: {issue_key}")
    issue = jira.issue(issue_key)
    print(f"   ✅ Found issue: {issue.fields.summary}")
    print(f"   📝 Description length: {len(issue.fields.description or '')} characters")
    return issue

