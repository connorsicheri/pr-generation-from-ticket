from __future__ import annotations

from app.prgen.context_parsing import TicketContext


def test_ticket_context_parses_paths_and_urls():
    desc = (
        "Update file {{src/app/main.py}} and `src/utils/helpers.ts`.\n"
        "Docs: https://your.atlassian.net/wiki/spaces/ENG/pages/12345/Spec\n"
        "Related PR: https://github.com/org/repo/pull/42\n"
        "Repo root (should be ignored as content): https://github.com/org/repo\n"
    )
    ctx = TicketContext(desc)
    assert "src/app/main.py" in ctx.file_paths
    assert "src/utils/helpers.ts" in ctx.file_paths
    assert any("atlassian.net" in u for u in ctx.confluence_urls)
    assert any("/pull/42" in u for u in ctx.github_pr_urls)
    assert not any(u.endswith("/org/repo") for u in ctx.generic_urls)


