from __future__ import annotations

from pathlib import Path
from textwrap import shorten
from typing import Dict, List


def gather_candidate_files(repo_path: Path, hinted_paths: List[str], budget_chars: int = 6000) -> Dict[str, str]:
    print(f"📂 Loading {len(hinted_paths)} file(s) from repository...")
    selected: Dict[str, str] = {}
    per_file_budget = max(budget_chars // max(len(hinted_paths), 1), 1)
    for rel in hinted_paths:
        p = repo_path / rel
        if not p.exists():
            print(f"   ⚠️  {rel} (will be created)")
            continue
        content = p.read_text("utf-8", errors="ignore")
        truncated_content = shorten(content, width=per_file_budget, placeholder="\n…\n")
        selected[rel] = truncated_content
        print(f"   ✅ {rel}")
    return selected

