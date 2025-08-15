from __future__ import annotations

import argparse

from .pipeline import run_pipeline


def main():
    print("🎆 AI PR Generator Starting...")
    print("=" * 50)
    parser = argparse.ArgumentParser(description="Generate a PR from a Jira ticket using Gemini")
    parser.add_argument("issue_key", help="Jira issue key, e.g. ENG-1234")
    args = parser.parse_args()
    print(f"🎫 Processing ticket: {args.issue_key}\n")
    run_pipeline(args.issue_key)


if __name__ == "__main__":
    main()

