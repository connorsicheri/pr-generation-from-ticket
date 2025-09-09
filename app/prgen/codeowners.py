from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import fnmatch


def parse_codeowners(repo_path: Path) -> List[tuple[str, List[str]]]:
    """Parse CODEOWNERS file into list of (pattern, owners).

    Supports patterns similar to .gitignore/CODEOWNERS semantics (basic fnmatch here).
    """
    for rel in ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]:
        p = repo_path / rel
        if p.exists():
            lines = p.read_text("utf-8", errors="ignore").splitlines()
            rules: List[tuple[str, List[str]]] = []
            for raw in lines:
                s = raw.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split()
                if len(parts) < 2:
                    continue
                pattern = parts[0]
                owners = [o.lstrip("@") for o in parts[1:]]
                rules.append((pattern, owners))
            return rules
    return []


def owners_for_paths(repo_path: Path, paths: List[str]) -> List[str]:
    rules = parse_codeowners(repo_path)
    owners: Dict[str, int] = {}
    for path in paths:
        for pattern, os_ in rules:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch("/" + path, pattern):
                for o in os_:
                    owners[o] = owners.get(o, 0) + 1
    # order by number of matches desc
    return [o for o, _ in sorted(owners.items(), key=lambda kv: (-kv[1], kv[0]))]


