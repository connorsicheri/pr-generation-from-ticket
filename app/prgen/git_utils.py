from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import List, Tuple


def run(cmd: List[str], cwd: str | Path | None = None, extra_env: dict | None = None):
    print(f"💻 Running: {' '.join(cmd)}")
    if cwd:
        print(f"   📁 Working directory: {cwd}")
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.returncode == 0:
        print("   ✅ Command completed successfully")
        return
    if proc.stderr:
        print("   🔻 stderr:")
        print(proc.stderr.strip())
    print(f"   ❌ Command failed with exit code {proc.returncode}")
    raise subprocess.CalledProcessError(proc.returncode, cmd)


def clone_and_branch(repo_url: str, desired_branch_name: str, workdir: Path) -> Tuple[Path, str]:
    print(f"🔄 Cloning repository...")
    print(f"   🔗 Repository: {repo_url}")
    repo_path = workdir / "repo"

    if repo_url.startswith('https://github.com/'):
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            auth_url = repo_url.replace('https://github.com/', f'https://{github_token}@github.com/')
            print(f"   🔐 Using GitHub token for authentication")
            run(["git", "clone", auth_url, str(repo_path)])
        else:
            print(f"   ⚠️  No GitHub token found, trying without authentication")
            run(["git", "clone", repo_url, str(repo_path)])
    else:
        if repo_url.startswith('git@'):
            print(f"   🔑 Using SSH authentication")
        run(["git", "clone", repo_url, str(repo_path)])

    final_branch = desired_branch_name
    try:
        subprocess.run(["git", "fetch", "origin", desired_branch_name], cwd=repo_path, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ls = subprocess.run(["git", "ls-remote", "--heads", "origin", desired_branch_name], cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        exists_remote = ls.returncode == 0 and ls.stdout.strip() != ""
        if exists_remote:
            actor = os.getenv("GITHUB_ACTOR", "runner")
            suffix = time.strftime("%Y%m%d%H%M%S")
            final_branch = f"{desired_branch_name}-{actor}-{suffix}"
            print(f"   ℹ️  Remote '{desired_branch_name}' exists; using '{final_branch}' to avoid non-fast-forward")
    except Exception as e:
        print(f"   ⚠️  Could not check remote branch existence: {e}")

    run(["git", "checkout", "-b", final_branch], cwd=repo_path)
    print(f"   🌿 Branch: {final_branch}")
    print(f"   ✅ Repository cloned and branch created")
    return repo_path, final_branch


def commit_push(repo_path: Path, branch_name: str, message: str):
    print(f"💾 Committing and pushing changes...")
    print(f"   📝 Commit message: {message}")
    print(f"   🌿 Target branch: {branch_name}")
    run(["git", "add", "-A"], cwd=repo_path)
    try:
        run(["git", "commit", "-m", message], cwd=repo_path)
    except subprocess.CalledProcessError:
        print("⚠️  No changes to commit – exiting.")
        raise SystemExit(0)

    trace_env = {
        "GIT_TRACE": "1",
        "GIT_TRACE_PACK_ACCESS": "1",
        "GIT_TRACE_PACKET": "1",
        "GIT_TRACE_PERFORMANCE": "1",
        "GIT_CURL_VERBOSE": "1",
    }
    try:
        run(["git", "push", "-u", "origin", branch_name], cwd=repo_path, extra_env=trace_env)
        print("   ✅ Changes committed and pushed successfully")
        return
    except subprocess.CalledProcessError:
        print("⚠️  Push failed. Collecting diagnostics…")
        for args in (
            ["git", "remote", "-v"],
            ["git", "status", "-sb"],
            ["git", "log", "--oneline", "-n", "10"],
            ["git", "fetch", "origin", branch_name],
            ["git", "ls-remote", "--heads", "origin", branch_name],
            ["git", "rev-parse", "HEAD"],
            ["git", "rev-parse", f"origin/{branch_name}"],
        ):
            try:
                run(args, cwd=repo_path)
            except Exception:
                pass
        raise

