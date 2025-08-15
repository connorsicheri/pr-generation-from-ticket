#!/usr/bin/env python3
"""
AI PR Generator Tool – Gemini Edition

Thin entrypoint that delegates to the modular package in `app/prgen/`.
"""
from __future__ import annotations

from prgen.cli import main


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n💥 Error occurred: {e}")
        print("🔍 Check the logs above for more details")
        raise

