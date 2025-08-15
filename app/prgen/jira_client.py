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


def get_related_links(jira: JIRA, issue) -> list[str]:
    """Return URLs from Jira "Related links" (remote issue links)."""
    urls: list[str] = []
    try:
        links = jira.remote_links(issue)
    except Exception:
        links = []
    for link in links or []:
        # RemoteLink may be dict-like or have attributes
        try:
            obj = getattr(link, 'object', None) or getattr(link, 'raw', {}).get('object') or {}
            url = None
            if isinstance(obj, dict):
                url = obj.get('url') or obj.get('icon', {}).get('url')
            if not url:
                url = getattr(link, 'url', None) or getattr(link, 'raw', {}).get('url')
            if url:
                urls.append(str(url))
        except Exception:
            continue
    # Deduplicate and strip trailing common punctuation
    clean = []
    seen = set()
    for u in urls:
        cu = str(u).rstrip('.,;)')
        if cu not in seen:
            clean.append(cu)
            seen.add(cu)
    if clean:
        print(f"🔗 Found {len(clean)} related link(s) in Jira: {clean}")
    return clean

