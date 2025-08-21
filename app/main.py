#!/usr/bin/env python3
"""
AI PR Generator Tool – Gemini Edition

Single CLI entrypoint that runs the top-level pipeline.
"""
from __future__ import annotations

import argparse
from app.pipeline import run_pipeline


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Generate and refine a PR from a Jira ticket")
        parser.add_argument("issue_key", help="Jira issue key, e.g. ENG-1234")
        args = parser.parse_args()
        run_pipeline(args.issue_key)
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n💥 Error occurred: {e}")
        print("🔍 Check the logs above for more details")
        raise

