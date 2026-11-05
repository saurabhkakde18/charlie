"""
tests/test_plugin_loader.py — Unit tests for plugin discovery and validation.
"""
from __future__ import annotations

from pathlib import Path
from core.plugin_loader import discover_plugins


def test_discover_plugins_with_good_and_malformed(tmp_path: Path):
    # 1. Good plugin
    good_file = tmp_path / "good_plugin.py"
    good_file.write_text('''
PLUGIN = {
    "name": "good_tool",
    "description": "A well-behaved plugin",
    "parameters": {"type": "OBJECT", "properties": {}},
}
def run(parameters: dict, player=None, session_memory=None) -> str:
    return "All good"
''', encoding="utf-8")

    # 2. Malformed: missing run()
    bad_file_1 = tmp_path / "no_run_plugin.py"
    bad_file_1.write_text('''
PLUGIN = {
    "name": "no_run_tool",
    "description": "Missing run function",
    "parameters": {"type": "OBJECT", "properties": {}},
}
''', encoding="utf-8")

    # 3. Malformed: missing PLUGIN dict
    bad_file_2 = tmp_path / "no_dict_plugin.py"
    bad_file_2.write_text('''
def run(parameters: dict, player=None, session_memory=None) -> str:
    return "Missing dict"
''', encoding="utf-8")

    # 4. Malformed: syntax error
    bad_file_3 = tmp_path / "syntax_err_plugin.py"
    bad_file_3.write_text('''
PLUGIN = { unclosed syntax
''', encoding="utf-8")

    logs = []
    reg = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: logs.append(m))

    decls = reg.get_tool_declarations()
    names = {d["name"] for d in decls}

    # Good plugin must be loaded and functional
    assert "good_tool" in names
    res = reg.run("good_tool", {})
    assert res == "All good"

    # Malformed plugins must NOT crash discovery, but must be skipped from valid declarations
    assert "no_run_tool" not in names
    assert "no_dict_plugin" not in names
    assert "syntax_err_plugin" not in names
