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


def summarize_text_with_gemini(text: str, label: str, char_limit: int = 1500) -> str:
    summary_prompt = (
        "You are assisting in software development. Summarize the following reference material "
        f"titled '{label}' into a concise developer brief under {char_limit} characters. "
        "Capture only the most relevant requirements, interfaces, decisions, and constraints. "
        "Do not include code fences or markdown, just plain text.\n\n"
        "--- BEGIN REFERENCE ---\n" + text + "\n--- END REFERENCE ---\n"
    )
    try:
        summarized = call_gemini(summary_prompt)
        return shorten(summarized, width=char_limit, placeholder="\n…\n")
    except Exception:
        return shorten(text, width=char_limit, placeholder="\n…\n")

