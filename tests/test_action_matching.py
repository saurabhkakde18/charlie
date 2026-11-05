"""
tests/test_action_matching.py — Unit tests for Action and Plugin name fuzzy matching.
"""
from __future__ import annotations

from pathlib import Path
from core.action_loader import discover_actions, ActionRegistry, ActionRecord
from core.plugin_loader import discover_plugins, PluginRegistry, PluginRecord


def test_action_registry_fuzzy_matching():
    records = {
        "web_search": ActionRecord(name="web_search", valid=True, handler=lambda parameters, **kw: "searched"),
        "file_controller": ActionRecord(name="file_controller", valid=True, handler=lambda parameters, **kw: "controlled"),
        "open_app": ActionRecord(name="open_app", valid=True, handler=lambda parameters, **kw: "opened"),
    }
    reg = ActionRegistry(actions=records, logger=lambda m: None)

    # 1. Exact match
    assert reg.resolve_name("web_search") == "web_search"
    assert reg.has("web_search")
    assert reg.run("web_search", {}) == "searched"

    # 2. Normalized match (missing underscore / case variation)
    assert reg.resolve_name("websearch") == "web_search"
    assert reg.has("websearch")
    assert reg.run("websearch", {}) == "searched"

    assert reg.resolve_name("filecontroller") == "file_controller"
    assert reg.has("filecontroller")
    assert reg.run("filecontroller", {}) == "controlled"

    # 3. Fuzzy match (minor typo)
    assert reg.resolve_name("open_ap") == "open_app"
    assert reg.has("open_ap")
    assert reg.run("open_ap", {}) == "opened"

    # 4. Unknown action returns None
    assert reg.resolve_name("totally_nonexistent_action") is None
    assert not reg.has("totally_nonexistent_action")
    assert "not available" in reg.run("totally_nonexistent_action", {})

