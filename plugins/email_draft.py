"""
plugins/email_draft.py — Email Draft Creator for Charlie.

Composes and opens an email draft in the system's default email client with
pre-filled recipient, subject, and body fields. Cross-platform.
"""
from __future__ import annotations

import urllib.parse
import webbrowser

PLUGIN = {
    "name": "email_draft",
    "description": (
        "Open the default email application with a pre-filled draft. "
        "Use when the user wants to email someone, send feedback, or draft a message."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "recipient": {"type": "STRING", "description": "Email address of the recipient (e.g. name@example.com)"},
            "subject": {"type": "STRING", "description": "Subject line of the email"},
            "body": {"type": "STRING", "description": "Body text of the message"},
            "cc": {"type": "STRING", "description": "Optional CC recipient email address"},
        },
        "required": ["recipient"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    recipient = str(parameters.get("recipient", "")).strip()
    subject = str(parameters.get("subject", "")).strip()
    body = str(parameters.get("body", "")).strip()
    cc = str(parameters.get("cc", "")).strip()

    if not recipient:
        return "Please specify a recipient email address."

    query_params = {}
    if subject:
        query_params["subject"] = subject
    if body:
        query_params["body"] = body
    if cc:
        query_params["cc"] = cc

    query_str = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)
    mailto_url = f"mailto:{urllib.parse.quote(recipient)}"
    if query_str:
        mailto_url += f"?{query_str}"

    try:
        opened = webbrowser.open(mailto_url)
        if not opened:
            return f"Draft created for {recipient}, but could not open default mail client."
    except Exception as e:
        return f"Failed to open email client: {e}"

    msg = f"Opened email draft to {recipient} with subject '{subject or '(No subject)'}'."
    if player:
        player.write_log(f"Charlie: {msg}")
    return msg
