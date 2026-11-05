"""
plugins/safe_shell.py — Safe Shell Execution with Strict Whitelist & Confirmation Gate for Charlie.

Allows running approved inspection/status commands. Anything outside the whitelist
or involving pipes/redirection is gated by core.confirm (UI-issued token).
"""
from __future__ import annotations

import platform
import shlex
import subprocess

from core import confirm
from core.logger import get_logger

logger = get_logger("safe_shell")

# Safe command prefixes that are read-only and harmless to execute
SAFE_WHITELIST = {
    "whoami", "hostname", "date", "time", "uptime", "pwd", "dir", "ls",
    "git status", "git log", "git branch", "git diff --stat",
    "python --version", "python -V", "pip --version", "pip list",
    "ipconfig", "ifconfig", "systeminfo", "uname", "df -h", "free -m",
}


def _is_strictly_whitelisted(cmd: str) -> bool:
    clean = cmd.strip()
    # Reject shell meta-characters and chaining immediately
    dangerous_chars = {"|", "&", ";", ">", "<", "`", "$", "(", ")", "\n", "\r"}
    if any(ch in clean for ch in dangerous_chars):
        return False

    lower = clean.lower()
    for safe in SAFE_WHITELIST:
        if lower == safe or lower.startswith(safe + " "):
            return True
    return False


def _execute(cmd: str) -> str:
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15.0,
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        combined = out or err or f"Command exited with code {res.returncode}"
        # Truncate if too long
        if len(combined) > 1500:
            combined = combined[:1500] + "\n... (truncated)"
        return combined
    except subprocess.TimeoutExpired:
        return f"Command '{cmd}' timed out after 15 seconds."
    except Exception as e:
        return f"Command execution error: {e}"


PLUGIN = {
    "name": "safe_shell",
    "description": (
        "Run terminal shell commands safely. Safe inspection commands run directly. "
        "Any modification, script, or unlisted command requires user confirmation on screen."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "The command line string to run"},
        },
        "required": ["command"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    cmd = str(parameters.get("command", "")).strip()
    if not cmd:
        return "Please provide a command to run."

    if _is_strictly_whitelisted(cmd):
        result = _execute(cmd)
        if player:
            player.show_content(f"Shell: {cmd}", result)
        return f"Output:\n{result}"

    # Outside whitelist -> Mandatory Confirmation Gate
    logger.warning(f"Command '{cmd}' is outside whitelist. Requesting UI confirmation.")
    return confirm.request(
        key=f"shell_{cmd[:30]}",
        title="Approve Shell Command",
        detail=f"Charlie is requesting to run:\n\n{cmd}\n\nApprove execution?",
        run=lambda: _execute(cmd),
    )

