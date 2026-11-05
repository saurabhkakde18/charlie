"""
actions/create_skill.py — Meta-Tool for Dynamic Skill Creation in Charlie.

When the user asks for a capability Charlie does not have, this tool generates
a new plugin in plugins/ from the template, displays the code on screen, and
ONLY installs and activates it after the user explicitly approves via the UI confirmation gate.
Never auto-executes unapproved code.
"""
from __future__ import annotations

import py_compile
import re
import sys
from pathlib import Path

from core import confirm
from core import gemini
from core.logger import get_logger

logger = get_logger("create_skill")

BASE_DIR = Path(__file__).resolve().parent.parent
PLUGINS_DIR = BASE_DIR / "plugins"
TEMPLATE_PATH = PLUGINS_DIR / "_template.py"

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")

TOOL = {
    "name": "create_skill",
    "description": (
        "Create a new custom skill/plugin for Charlie when asked for a capability Charlie cannot do yet. "
        "Generates code from template, displays it for user review, and requests UI approval before loading."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "skill_name": {
                "type": "STRING",
                "description": "Unique snake_case identifier for the new skill (e.g. 'stock_ticker', 'currency_converter')",
            },
            "description": {
                "type": "STRING",
                "description": "Clear explanation of what the new skill does and what triggers it",
            },
            "code": {
                "type": "STRING",
                "description": "Optional Python implementation of the plugin. If omitted, Charlie synthesizes it from template.",
            },
        },
        "required": ["skill_name", "description"],
    },
}


def _generate_skill_code(skill_name: str, description: str, raw_code: str = "") -> str:
    if raw_code and "PLUGIN" in raw_code and "def run(" in raw_code:
        # User/model provided code directly
        clean = raw_code.strip()
        if clean.startswith("```python"):
            clean = clean[9:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    prompt = (
        f"You are creating a new plugin for personal assistant Charlie named '{skill_name}'.\n"
        f"Purpose: {description}\n\n"
        "Rules:\n"
        "1. Define PLUGIN dict with 'name', 'description', 'parameters' (type OBJECT, properties, required).\n"
        "2. Define def run(parameters: dict, player=None, session_memory=None) -> str:\n"
        "3. Threading: NEVER import or touch PyQt6 or Qt widgets! Use thread-safe player.write_log() or player.show_content().\n"
        "4. Catch all exceptions inside run() and return a helpful sentence — NEVER raise.\n"
        "5. Output valid, clean Python code only. No markdown fences, no explanation."
    )
    res = gemini.text(prompt, tier=gemini.SMART, timeout_ms=25_000)
    if not res:
        # Fallback template
        res = f'''"""
plugins/{skill_name}.py — Auto-generated skill for Charlie.
"""
from __future__ import annotations

PLUGIN = {{
    "name": "{skill_name}",
    "description": "{description}",
    "parameters": {{
        "type": "OBJECT",
        "properties": {{
            "query": {{"type": "STRING", "description": "Input for this skill"}},
        }},
        "required": [],
    }},
}}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        query = parameters.get("query", "")
        result = f"Completed {skill_name} with input: {{query}}"
        if player:
            player.write_log(f"Charlie: {{result}}")
        return result
    except Exception as e:
        return f"Error executing {skill_name}: {{e}}"
'''
    clean = res.strip()
    clean = re.sub(r"^```[a-zA-Z]*\n?", "", clean)
    clean = re.sub(r"\n?```$", "", clean)
    return clean.strip()


def run(parameters: dict, player=None, session_memory=None) -> str:
    skill_name = str(parameters.get("skill_name", "")).strip().lower()
    description = str(parameters.get("description", "")).strip()
    raw_code = str(parameters.get("code", "")).strip()

    if not skill_name or not _NAME_RE.match(skill_name):
        return f"Invalid skill name '{skill_name}'. Must be a snake_case identifier."
    if not description:
        return "Please provide a description of what the skill does."

    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = PLUGINS_DIR / f"{skill_name}.py"
    pending_path = PLUGINS_DIR / f"_{skill_name}_pending.py"

    if target_path.exists():
        return f"A plugin named '{skill_name}' already exists in plugins/."

    # Generate and validate code
    code = _generate_skill_code(skill_name, description, raw_code)

    # Write to pending file (ignored by plugin loader because of leading underscore)
    pending_path.write_text(code, encoding="utf-8")

    # Syntax verification
    try:
        py_compile.compile(str(pending_path), doraise=True)
    except Exception as e:
        if pending_path.exists():
            pending_path.unlink()
        return f"Generated code failed syntax check: {e}"

    # Display code in UI
    if player:
        player.show_content(f"Generated Skill: {skill_name}", code)

    def _approve_and_install() -> str:
        try:
            if not pending_path.exists():
                return f"Pending file for '{skill_name}' was not found."
            # Move pending to final plugin location
            pending_path.replace(target_path)
            logger.info(f"Installed new plugin: {target_path}")

            # Notify UI
            if player:
                player.write_log(f"Charlie: Skill '{skill_name}' approved and installed.")

            return f"Skill '{skill_name}' has been approved, installed, and loaded into Charlie."
        except Exception as e:
            logger.error(f"Failed to install skill '{skill_name}': {e}")
            return f"Error installing skill '{skill_name}': {e}"

    # Park behind Confirmation Gate: requires UI button click
    logger.info(f"Skill '{skill_name}' generated. Requesting UI approval.")
    return confirm.request(
        key=f"skill_install_{skill_name}",
        title=f"Install Skill: {skill_name}",
        detail=(
            f"Charlie generated a new skill:\n\n"
            f"Name: {skill_name}\nDescription: {description}\n\n"
            f"Review the code in the display panel. Press Confirm to install and activate."
        ),
        run=_approve_and_install,
    )


TOOL["handler"] = run


