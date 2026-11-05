"""
tests/test_memory_manager.py — Unit tests for Charlie's Long-Term Memory System.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from memory import memory_manager as mm


def test_memory_crud(tmp_path: Path):
    test_db = tmp_path / "test_memory.json"
    with patch("memory.memory_manager.MEMORY_PATH", test_db):
        # 1. Initially empty
        data = mm.load_memory()
        assert isinstance(data, dict)

        # 2. Add preference
        mm.update_memory({"preferences": {"theme": "dark_amber"}})
        loaded = mm.load_memory()
        assert loaded.get("preferences", {}).get("theme", {}).get("value") == "dark_amber"

        # 3. Add identity
        mm.update_memory({"identity": {"language": "Hindi"}})
        loaded2 = mm.load_memory()
        assert loaded2.get("identity", {}).get("language", {}).get("value") == "Hindi"

        # 4. Search memory
        found = mm.search_memory("theme")
        assert "dark_amber" in found

        # 5. Format for prompt
        prompt_block = mm.format_memory_for_prompt(loaded2)
        assert "Hindi" in prompt_block or "dark_amber" in prompt_block
