from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class PolicyConfig:
    allow_patterns: List[str]
    deny_patterns: List[str]
    max_files: int
    max_total_bytes: int
    max_file_bytes: int


DEFAULT_DENY_PATTERNS: List[str] = [
    ".git/**",
    ".github/workflows/**",
    ".github/actions/**",
    ".github/ISSUE_TEMPLATE/**",
    ".github/CODEOWNERS",
    ".env",
    ".env.*",
    "**/.ssh/**",
    "**/id_rsa*",
    "**/id_dsa*",
    "**/*.pem",
    "**/*.key",
    "**/*.p12",
    "**/*.keystore",
    "**/*.jks",
    "**/*secret*",
    "**/*token*",
]


def _split_csv_env(name: str) -> List[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def load_policy_config(env: Optional[dict] = None) -> PolicyConfig:
    """Load policy configuration from the provided env or process env.

    Env vars:
      - AI_PR_ALLOW_PATHS: comma-separated globs to allow (optional)
      - AI_PR_DENY_PATHS: comma-separated globs to additionally deny
      - AI_PR_MAX_PATCH_FILES: maximum files allowed per patch application
      - AI_PR_MAX_PATCH_BYTES: maximum total bytes across all files
      - AI_PR_MAX_FILE_BYTES: maximum bytes per single file
    """
    getenv = (env or os.environ).get
    allow = _split_csv_env("AI_PR_ALLOW_PATHS") if env is None else [p.strip() for p in (getenv("AI_PR_ALLOW_PATHS", "").split(",")) if p.strip()]
    deny_extra = _split_csv_env("AI_PR_DENY_PATHS") if env is None else [p.strip() for p in (getenv("AI_PR_DENY_PATHS", "").split(",")) if p.strip()]

    max_files = int(getenv("AI_PR_MAX_PATCH_FILES", 30))
    max_total_bytes = int(getenv("AI_PR_MAX_PATCH_BYTES", 300000))
    max_file_bytes = int(getenv("AI_PR_MAX_FILE_BYTES", 120000))

    return PolicyConfig(
        allow_patterns=allow,
        deny_patterns=[*DEFAULT_DENY_PATTERNS, *deny_extra],
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        max_file_bytes=max_file_bytes,
    )


def _path_matches_any(rel_path: str, patterns: List[str]) -> bool:
    if not patterns:
        return False
    return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)


def validate_and_normalize_changes(
    changes: List[dict], repo_path: Path, config: Optional[PolicyConfig] = None
) -> List[dict]:
    """Validate policy, normalize, and return accepted changes.

    - Ensures paths are relative and within the repository
    - Enforces allow/deny patterns
    - Enforces max files and size limits (per-file and total)
    - Returns list of {path, content} with normalized repo-relative paths
    """
    if not isinstance(changes, list):
        raise ValueError("Changes must be a list of {path, content} objects")

    cfg = config or load_policy_config()
    repo_root = repo_path.resolve()

    normalized: List[dict] = []
    total_bytes = 0
    violations: List[str] = []

    for idx, fc in enumerate(changes, start=1):
        if not isinstance(fc, dict):
            raise ValueError(f"Change #{idx} is not an object")
        if "path" not in fc or "content" not in fc:
            raise ValueError(f"Change #{idx} missing 'path' or 'content'")

        raw_path = str(fc["path"]).strip()
        if raw_path == "":
            raise ValueError(f"Change #{idx} has empty path")

        p_rel = Path(raw_path)
        if p_rel.is_absolute():
            raise ValueError(f"Change '{raw_path}' is an absolute path; only relative paths are allowed")

        candidate = (repo_root / p_rel).resolve()
        try:
            candidate.relative_to(repo_root)
        except Exception:
            raise ValueError(f"Change '{raw_path}' escapes repository root via path traversal")

        rel_str = str(candidate.relative_to(repo_root)).replace("\\", "/")

        if _path_matches_any(rel_str, cfg.deny_patterns):
            violations.append(f"DENY: '{rel_str}' matches a protected pattern")
            continue

        if cfg.allow_patterns and not _path_matches_any(rel_str, cfg.allow_patterns):
            violations.append(f"NOT ALLOWED: '{rel_str}' not in AI_PR_ALLOW_PATHS")
            continue

        content = fc["content"]
        if not isinstance(content, str):
            raise ValueError(f"Change '{rel_str}' content must be string")
        size_bytes = len(content.encode("utf-8"))
        if size_bytes > cfg.max_file_bytes:
            violations.append(
                f"FILE TOO LARGE: '{rel_str}' is {size_bytes} bytes, limit is {cfg.max_file_bytes}"
            )
            continue

        total_bytes += size_bytes
        normalized.append({"path": rel_str, "content": content})

    if violations:
        preview = "\n".join([f" - {v}" for v in violations[:10]])
        more = "" if len(violations) <= 10 else f"\n - … and {len(violations) - 10} more"
        raise ValueError(
            "Policy blocked one or more changes:\n"
            f"{preview}{more}\n\n"
            "To allow specific paths, set AI_PR_ALLOW_PATHS and/or relax AI_PR_DENY_PATHS."
        )

    if len(normalized) > cfg.max_files:
        raise ValueError(
            f"Too many files in patch: {len(normalized)} > {cfg.max_files}. "
            "Adjust AI_PR_MAX_PATCH_FILES if needed."
        )

    if total_bytes > cfg.max_total_bytes:
        raise ValueError(
            f"Patch too large: {total_bytes} bytes > {cfg.max_total_bytes} bytes. "
            "Adjust AI_PR_MAX_PATCH_BYTES or split into smaller changes."
        )

    return normalized


