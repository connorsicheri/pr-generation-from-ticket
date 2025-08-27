from __future__ import annotations

"""Top-level package for the AI PR Generator.

This package contains the orchestration entrypoints and agent logic used to
generate and iteratively refine pull requests from Jira tickets.
"""

# Public package version
__version__ = "0.1.0"

# Convenience export so consumers can do: `from app import run_pipeline`
try:
    from .pipeline import run_pipeline  # noqa: F401
    __all__ = ["run_pipeline", "__version__"]
except Exception:  # pragma: no cover - safe fallback if import-time deps missing
    __all__ = ["__version__"]

