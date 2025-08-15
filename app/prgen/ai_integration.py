from __future__ import annotations

import os
from textwrap import shorten

import google.generativeai as genai


def call_gemini(prompt: str) -> str:
    print(f"🤖 Generating code with {os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')}...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var missing.")
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    result = response.text.strip()
    print(f"   ✅ Generated {len(result)} characters of code")
    return result


def summarize_text_with_gemini(text: str, label: str, char_limit: int = 1500, ticket_summary: str | None = None, ticket_instructions: str | None = None) -> str:
    contextual_prefix = ""
    if ticket_summary or ticket_instructions:
        contextual_prefix = (
            ("Ticket summary:\n" + (ticket_summary or "") + "\n\n") +
            ("Ticket instructions:\n" + (ticket_instructions or "") + "\n\n")
        )
    summary_prompt = (
        "You are assisting in software development. Summarize the following reference material "
        f"titled '{label}' into a concise developer brief under {char_limit} characters. "
        "Extract ONLY information that materially helps implement the ticket. Focus on APIs, data models, acceptance criteria, constraints, decisions, file/function identifiers. Ignore irrelevant background. "
        "Do not include code fences or markdown, just plain text.\n\n"
        + contextual_prefix +
        "--- BEGIN REFERENCE ---\n" + text + "\n--- END REFERENCE ---\n"
    )
    try:
        summarized = call_gemini(summary_prompt)
        return shorten(summarized, width=char_limit, placeholder="\n…\n")
    except Exception:
        return shorten(text, width=char_limit, placeholder="\n…\n")


def synthesize_summaries_with_gemini(summaries_block: str, ticket_summary: str, ticket_instructions: str, char_limit: int = 2000) -> str:
    prompt = (
        "You are assisting in software development. Create a cohesive, de-duplicated brief from multiple source summaries. "
        f"Limit to {char_limit} characters. Focus on actionable implementation details and constraints.\n\n"
        "Ticket summary:\n" + (ticket_summary or "") + "\n\n"
        "Ticket instructions:\n" + (ticket_instructions or "") + "\n\n"
        "Reference summaries:\n" + summaries_block + "\n\n"
        "Output plain text only."
    )
    try:
        result = call_gemini(prompt)
        return shorten(result, width=char_limit, placeholder="\n…\n")
    except Exception:
        return shorten(summaries_block, width=char_limit, placeholder="\n…\n")

