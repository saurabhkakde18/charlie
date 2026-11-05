"""
plugins/screen_describe.py — Screenshot & Screen Description for Charlie.

Captures the user's primary screen and generates a natural-language description
of what is visible, open applications, or specific elements the user asks about.
"""
from __future__ import annotations

import io
from pathlib import Path
from PIL import Image

from core import gemini
from core.logger import get_logger

logger = get_logger("screen_describe")


def _capture_screen_bytes() -> bytes:
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        from PIL import ImageGrab
        img = ImageGrab.grab()

    # Resize to reasonable dimension for fast vision inference
    img.thumbnail((1280, 720))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


PLUGIN = {
    "name": "screen_describe",
    "description": (
        "Take a screenshot and describe what is currently visible on the user's screen. "
        "Use when the user asks 'what is on my screen?', 'look at this', or asks questions about visible windows or code."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "question": {
                "type": "STRING",
                "description": "Optional specific question about what is on screen (e.g. 'what error is showing?', 'summarize this document')",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    question = str(parameters.get("question", "")).strip()

    try:
        img_bytes = _capture_screen_bytes()
    except Exception as e:
        logger.error(f"Failed to capture screen: {e}")
        return f"Could not capture screenshot: {e}"

    prompt = (
        "You are looking at a screenshot of the user's computer screen. "
        f"{f'Answer this question specifically: {question}' if question else 'Describe what is open, main active windows, and any prominent text or errors.'}\n"
        "Be concise, concrete, and helpful in 2-4 sentences."
    )

    contents = [
        {"role": "user", "parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": img_bytes}}]}
    ]

    try:
        resp = gemini.call(contents, tier=gemini.SMART, timeout_ms=20_000)
        desc = ""
        if resp and resp.text:
            desc = resp.text.strip()
        elif resp and resp.candidates:
            parts = getattr(resp.candidates[0].content, "parts", [])
            desc = "".join(p.text for p in parts if getattr(p, "text", "")).strip()
    except Exception as e:
        return f"Vision model error: {e}"

    if not desc:
        return "Captured screen, but could not describe its contents."

    if player:
        player.show_content("Screen Observation", desc)
        player.write_log(f"Charlie: Inspected screen.")

    return desc
