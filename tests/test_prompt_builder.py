from __future__ import annotations

from app.prgen.context_parsing import TicketContext
from app.prgen.prompt_builder import build_prompt


class DummyIssue:
    class Fields:
        def __init__(self):
            self.summary = "Add header to workflow"
            self.description = "Update {{.github/workflows/build.yaml}} with header"
    def __init__(self):
        self.key = "ENG-1"
        self.fields = DummyIssue.Fields()


def test_build_prompt_includes_sections():
    issue = DummyIssue()
    ctx = TicketContext(issue.fields.description)
    repo_snips = {".github/workflows/build.yaml": "name: build"}
    external = {"SYNTHESIS": "Important constraints"}
    prompt = build_prompt(issue, ctx, repo_snips, external)
    assert "Ticket summary" in prompt
    assert "Repository snippets" in prompt
    assert "External references" in prompt
    assert "BEGIN FILE .github/workflows/build.yaml" in prompt


