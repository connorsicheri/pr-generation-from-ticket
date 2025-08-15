from __future__ import annotations

import os
from github import Github


def get_github_client() -> Github:
    token = os.environ["GITHUB_TOKEN"]
    return Github(token)


def create_pull_request(gh: Github, repo_full_name: str, branch: str, base: str, title: str, body: str):
    print(f"🔄 Creating pull request...")
    print(f"   📁 Repository: {repo_full_name}")
    print(f"   🌿 Source branch: {branch}")
    print(f"   🌿 Target branch: {base}")
    print(f"   🏷️ Title: {title}")
    repo = gh.get_repo(repo_full_name)
    pr = repo.create_pull(title=title, body=body, head=branch, base=base)
    print(f"   ✅ Pull request created: #{pr.number}")
    print(f"   🔗 URL: {pr.html_url}")
    return pr

