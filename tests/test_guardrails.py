from pathlib import Path
import os

from app.prgen.guardrails import validate_and_normalize_changes, load_policy_config, PolicyConfig


def test_reject_absolute_and_traversal(tmp_path: Path):
    cfg = PolicyConfig(allow_patterns=[], deny_patterns=[], max_files=10, max_total_bytes=10000, max_file_bytes=5000)
    # absolute
    try:
        validate_and_normalize_changes([{"path": "/etc/passwd", "content": "x"}], tmp_path, cfg)
        assert False, "should have rejected absolute path"
    except ValueError as e:
        assert "absolute" in str(e)
    # traversal
    try:
        validate_and_normalize_changes([{"path": "../outside.txt", "content": "x"}], tmp_path, cfg)
        assert False, "should have rejected traversal"
    except ValueError as e:
        assert "escapes" in str(e)


def test_deny_and_allow_patterns(tmp_path: Path):
    cfg = PolicyConfig(allow_patterns=["src/**"], deny_patterns=["src/secrets/**"], max_files=10, max_total_bytes=10000, max_file_bytes=5000)
    # allowed path
    accepted = validate_and_normalize_changes([{"path": "src/app.py", "content": "print('hi')"}], tmp_path, cfg)
    assert len(accepted) == 1
    # denied path
    try:
        validate_and_normalize_changes([{"path": "src/secrets/key.pem", "content": "k"}], tmp_path, cfg)
        assert False, "should have denied path"
    except ValueError as e:
        assert "DENY" in str(e)
    # not in allow list
    try:
        validate_and_normalize_changes([{"path": "other/app.py", "content": "ok"}], tmp_path, cfg)
        assert False, "should have rejected not-in-allow"
    except ValueError as e:
        assert "NOT ALLOWED" in str(e)


def test_limits(tmp_path: Path):
    cfg = PolicyConfig(allow_patterns=[], deny_patterns=[], max_files=1, max_total_bytes=5, max_file_bytes=5)
    # too many files
    try:
        validate_and_normalize_changes([
            {"path": "a.txt", "content": "1"},
            {"path": "b.txt", "content": "2"},
        ], tmp_path, cfg)
        assert False, "should have rejected too many files"
    except ValueError as e:
        assert "Too many files" in str(e)
    # too large file
    try:
        validate_and_normalize_changes([
            {"path": "big.txt", "content": "123456"},
        ], tmp_path, cfg)
        assert False, "should have rejected big file"
    except ValueError as e:
        assert "FILE TOO LARGE" in str(e)
    # too large total
    try:
        validate_and_normalize_changes([
            {"path": "ok.txt", "content": "1234"},
            {"path": "ok2.txt", "content": "2"},
        ], tmp_path, cfg)
        assert False, "should have rejected big total"
    except ValueError as e:
        assert "Patch too large" in str(e)


