"""
plugins/translator.py — Live Language and Text Translation for Charlie.

Translates words, sentences, or paragraphs into any target language using
core.gemini.
"""
from __future__ import annotations

from core import gemini

PLUGIN = {
    "name": "translator",
    "description": (
        "Translate text into any target language. "
        "Use when the user asks to translate text, a sentence, or words into another language."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {"type": "STRING", "description": "The text or phrase to translate"},
            "target_language": {"type": "STRING", "description": "The target language (e.g. 'Spanish', 'Hindi', 'Japanese', 'German', 'Turkish', 'French')"},
            "source_language": {"type": "STRING", "description": "Optional source language if known"},
        },
        "required": ["text", "target_language"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    text = str(parameters.get("text", "")).strip()
    target_lang = str(parameters.get("target_language", "")).strip()
    source_lang = str(parameters.get("source_language", "")).strip()

    if not text:
        return "Please provide text to translate."
    if not target_lang:
        return "Please specify the target language."

    prompt = (
        f"You are a professional translator. Translate the following text into {target_lang}. "
        f"{f'Source language is {source_lang}.' if source_lang else ''}\n"
        "Preserve meaning, natural colloquial register, and nuance. "
        "Output ONLY the translated text without commentary or quotation marks.\n\n"
        f"Text to translate:\n{text}"
    )

    try:
        translated = gemini.text(prompt, tier=gemini.FAST, timeout_ms=10_000)
        if not translated:
            translated = gemini.text(prompt, tier=gemini.SMART, timeout_ms=15_000)
    except Exception as e:
        return f"Translation service error: {e}"

    if not translated:
        return f"Could not translate text into {target_lang}."

    translated = translated.strip()

    if player:
        player.show_content(f"Translation ({target_lang})", f"Original:\n{text}\n\nTranslation:\n{translated}")
        player.write_log(f"Charlie: [{target_lang}] {translated}")

    return f"In {target_lang}: {translated}"

