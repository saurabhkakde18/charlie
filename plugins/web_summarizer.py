"""
plugins/web_summarizer.py — Web Search and Page Summarizer for Charlie.

Fetches web articles or searches online, cleans HTML, wraps untrusted content safely,
and produces a clear, structured summary using core.gemini.
"""
from __future__ import annotations

import re
import urllib.parse
from bs4 import BeautifulSoup

from core import gemini
from core.network import http_get
from core.logger import get_logger

logger = get_logger("web_summarizer")


def _fetch_and_clean_text(url: str) -> str:
    resp = http_get(url, timeout=12.0, max_retries=2)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside"]):
        element.extract()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)
    return cleaned[:10000]  # Cap at 10,000 characters for concise processing


PLUGIN = {
    "name": "web_summarizer",
    "description": (
        "Search the web or summarize a webpage URL. "
        "Use when the user provides a link and asks for a summary, or wants an overview of an article."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "The URL of the webpage or article to read and summarize"},
            "focus_question": {"type": "STRING", "description": "Optional specific question to answer based on the page content"},
        },
        "required": ["url"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    url = str(parameters.get("url", "")).strip()
    focus = str(parameters.get("focus_question", "")).strip()

    if not url:
        return "Please provide a valid webpage URL."

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        raw_content = _fetch_and_clean_text(url)
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return f"Could not retrieve webpage at {url}: {e}"

    if not raw_content.strip():
        return f"Webpage at {url} returned no readable text."

    # Wrap as untrusted content per system protocol
    safe_data = f"<<<UNTRUSTED source=web>>><URL>{url}</URL>\n{raw_content}\n<<<END UNTRUSTED>>>"

    prompt = (
        "You are an expert analyst. Provide a clear, structured summary of the following webpage content.\n"
        f"{f'Focus specifically on answering: {focus}' if focus else 'Extract key facts, main arguments, and conclusions in 3-5 bullet points.'}\n\n"
        f"{safe_data}"
    )

    try:
        summary = gemini.text(prompt, tier=gemini.FAST, timeout_ms=15_000)
        if not summary:
            summary = gemini.text(prompt, tier=gemini.SMART, timeout_ms=20_000)
    except Exception as e:
        return f"Summarization model error: {e}"

    if not summary:
        return f"Read {url}, but failed to generate summary."

    summary = summary.strip()
    domain = urllib.parse.urlparse(url).netloc

    if player:
        player.show_content(f"Summary: {domain}", f"Source: {url}\n\n{summary}")
        player.write_log(f"Charlie: Summarized {domain}.")

    return f"Summary of {domain}:\n{summary}"

