from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse, parse_qs
import html as html_lib

import requests
from github import Github
from textwrap import shorten


def _strip_html(html: str) -> str:
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return text.strip()


def fetch_confluence_page(url: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path
    page_id_match = re.search(r"/pages/(\d+)", path)
    page_id = None
    if page_id_match:
        page_id = page_id_match.group(1)
    else:
        qs = parse_qs(parsed.query)
        if 'pageId' in qs and qs['pageId']:
            page_id = qs['pageId'][0]
    if not page_id:
        raise ValueError(f"Could not extract Confluence pageId from URL: {url}")

    api = f"{base}/wiki/rest/api/content/{page_id}?expand=body.view,title"
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_TOKEN")
    if not email or not token:
        raise RuntimeError("JIRA_EMAIL and JIRA_TOKEN are required to read Confluence content")

    print(f"📘 Fetching Confluence page {page_id} …")
    timeout = int(os.getenv("EXTERNAL_FETCH_TIMEOUT_MS", "10000")) / 1000.0
    resp = requests.get(api, auth=(email, token), timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Confluence API error {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    title = data.get("title", "Untitled")
    html = (data.get("body", {}).get("view", {}) or {}).get("value", "")
    text = _strip_html(html)
    print(f"   ✅ Confluence: '{title}' ({len(text)} chars)")
    return title, text


def fetch_github_pr_context(gh: Github, pr_url: str, per_file_budget: int = 3000) -> Dict[str, str]:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError(f"Unsupported PR URL: {pr_url}")
    owner, repo, num_str = m.group(1), m.group(2), m.group(3)
    repo_full = f"{owner}/{repo}"
    print(f"📦 Fetching GitHub PR {repo_full}#{num_str} …")
    repo_obj = gh.get_repo(repo_full)
    pr = repo_obj.get_pull(int(num_str))

    sections: Dict[str, str] = {}
    header = f"Title: {pr.title}\nAuthor: {pr.user.login if pr.user else 'unknown'}\nState: {pr.state}\nURL: {pr.html_url}\n\nBody:\n{pr.body or ''}"
    sections["PR"] = shorten(header, width=per_file_budget, placeholder="\n…\n")

    files_limit = int(os.getenv("GITHUB_PR_FILES_LIMIT", "50"))
    try:
        files = list(pr.get_files())
    except Exception:
        files = []
    file_text_parts: List[str] = []
    for f in files[:files_limit]:
        file_header = f"--- {f.filename} ({f.status}, +{f.additions}/-{f.deletions}) ---\n"
        patch = getattr(f, "patch", None) or ""
        file_text_parts.append(file_header + shorten(patch, width=per_file_budget, placeholder="\n…\n"))
    if file_text_parts:
        sections["FILES"] = "\n".join(file_text_parts)
    print(f"   ✅ PR files: {len(files)}")
    return sections


def fetch_generic_page(url: str) -> Tuple[str, str]:
    timeout = int(os.getenv("EXTERNAL_FETCH_TIMEOUT_MS", "10000")) / 1000.0
    print(f"🌐 Fetching generic page: {url}")
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ai-pr-generator/1.0"})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    content_type = resp.headers.get("Content-Type", "")
    text = resp.text
    if "html" in content_type:
        text = _strip_html(text)
    title = url
    print(f"   ✅ Generic page length: {len(text)} chars")
    return title, text

