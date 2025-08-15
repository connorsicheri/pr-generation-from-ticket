from __future__ import annotations

import re
from typing import List, Tuple


class TicketContext:
    """Extract file paths, external references, and free‑form instructions from a ticket."""

    def __init__(self, description: str):
        self.description = description or ""
        (
            self.file_paths,
            self.confluence_urls,
            self.github_pr_urls,
            self.instructions,
        ) = self._parse(self.description)

    @staticmethod
    def _parse(text: str) -> Tuple[List[str], List[str], List[str], str]:
        file_regex = re.compile(r"\{\{([^{}\n]*[/\\]?[^{}\n/\\]*\.(?:py|go|js|ts|tsx|java|yaml|json|yml|md|txt|sh|jsx|vue|php|rb|cpp|c|h))\}\}")
        paths = file_regex.findall(text)

        backtick_regex = re.compile(r"`([^`\n]*[/\\]?[^`\n/\\]*\.(?:py|go|js|ts|tsx|java|yaml|json|yml|md|txt|sh|jsx|vue|php|rb|cpp|c|h))`")
        backtick_paths = backtick_regex.findall(text)

        all_paths = paths + backtick_paths

        cleaned_paths: List[str] = []
        for path in all_paths:
            cleaned_path = path.strip()
            if cleaned_path.startswith('./'):
                cleaned_path = cleaned_path[2:]
            cleaned_path = cleaned_path.replace('\\', '/')
            cleaned_paths.append(cleaned_path)

        url_regex = re.compile(r"https?://[^\s)]+")
        all_urls = url_regex.findall(text)
        confluence_urls: List[str] = []
        github_pr_urls: List[str] = []
        for u in all_urls:
            if 'atlassian.net/wiki' in u or '/wiki/spaces/' in u or 'confluence' in u:
                confluence_urls.append(u.rstrip('.,;)'))
            if re.search(r"https://github\.com/[^/]+/[^/]+/pull/\d+", u):
                github_pr_urls.append(u.rstrip('.,;)'))

        instructions = re.sub(file_regex, "", text)
        instructions = re.sub(backtick_regex, "", instructions).strip()
        return cleaned_paths, confluence_urls, github_pr_urls, instructions

