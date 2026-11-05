"""
plugins/code_project_helper.py — Developer Project Companion for Charlie.

Capabilities:
  • Open project in editor (VS Code, Cursor, or system file manager).
  • Run tests (pytest, npm test, cargo test, etc.) and capture output.
  • Analyze and show errors clearly on screen via player.show_review.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core import gemini
from core.logger import get_logger

logger = get_logger("code_project_helper")

PLUGIN = {
    "name": "code_project_helper",
    "description": (
        "Open developer projects, run automated tests, and analyze error traces. "
        "Use when the user wants to open a repository, run tests (pytest/npm/cargo), or debug failures."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: 'open_project', 'run_tests', 'show_errors'",
            },
            "project_path": {"type": "STRING", "description": "Absolute or relative path to the project directory"},
            "test_command": {"type": "STRING", "description": "Custom test command (e.g. 'pytest', 'npm test'). Defaults to auto-detecting test runner."},
        },
        "required": ["action"],
    },
}


def _auto_detect_test_command(path: Path) -> str:
    if (path / "pytest.ini").exists() or (path / "tests").is_dir() or list(path.glob("test_*.py")):
        return f'"{path / ".venv" / "Scripts" / "pytest"}"' if (path / ".venv" / "Scripts" / "pytest.exe").exists() else "pytest"
    if (path / "package.json").exists():
        return "npm test"
    if (path / "Cargo.toml").exists():
        return "cargo test"
    if (path / "go.mod").exists():
        return "go test ./..."
    return "pytest"


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip().lower()
    path_str = str(parameters.get("project_path", "")).strip() or str(Path.cwd())
    test_cmd = str(parameters.get("test_command", "")).strip()

    proj_dir = Path(path_str).resolve()
    if not proj_dir.is_dir():
        return f"Project directory '{proj_dir}' does not exist."

    if action == "open_project":
        # Check available editors
        editor = None
        for cand in ("code", "cursor", "pycharm", "subl"):
            if shutil.which(cand):
                editor = cand
                break

        try:
            if editor:
                subprocess.Popen([editor, str(proj_dir)], creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                msg = f"Opened project '{proj_dir.name}' in {editor}."
            else:
                # Fallback to system explorer
                if os.name == "nt":
                    subprocess.Popen(["explorer", str(proj_dir)])
                else:
                    subprocess.Popen(["xdg-open", str(proj_dir)])
                msg = f"Opened project directory '{proj_dir.name}'."
            if player:
                player.write_log(f"Charlie: {msg}")
            return msg
        except Exception as e:
            return f"Failed to open project: {e}"

    elif action == "run_tests":
        cmd = test_cmd or _auto_detect_test_command(proj_dir)
        logger.info(f"Running tests in {proj_dir} with: {cmd}")
        try:
            res = subprocess.run(
                cmd,
                cwd=str(proj_dir),
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60.0,
            )
            out = (res.stdout or "") + "\n" + (res.stderr or "")
            passed = res.returncode == 0
            status_text = "Tests Passed ✅" if passed else f"Tests Failed ❌ (exit code {res.returncode})"

            # Store last test run result in project dir for show_errors
            log_dest = proj_dir / ".test_run.log"
            try:
                log_dest.write_text(out, encoding="utf-8")
            except Exception:
                pass

            if player:
                findings = []
                for line in out.splitlines():
                    if "FAILED" in line or "ERROR" in line or "error" in line.lower():
                        findings.append(line.strip())
                player.show_review(
                    f"Test Results: {proj_dir.name}",
                    status_text,
                    findings[:8] or ["All test suites executed."],
                )

            summary = f"{status_text}\n" + (out[-800:] if len(out) > 800 else out)
            return summary
        except subprocess.TimeoutExpired:
            return "Test execution timed out after 60 seconds."
        except Exception as e:
            return f"Failed to run tests: {e}"

    elif action == "show_errors":
        log_file = proj_dir / ".test_run.log"
        if not log_file.exists():
            return "No recent test output log found. Run 'run_tests' first."
        raw_errors = log_file.read_text(encoding="utf-8", errors="replace")
        if not raw_errors.strip():
            return "Last test output was empty."

        prompt = (
            "Analyze the following test failure output. "
            "Identify the root cause, failing file, and recommend a clear concise fix in 2-3 sentences:\n\n"
            f"{raw_errors[:3000]}"
        )
        analysis = gemini.text(prompt, tier=gemini.FAST, timeout_ms=12_000)
        summary = analysis or raw_errors[-500:]

        if player:
            player.show_content(f"Error Analysis: {proj_dir.name}", summary)
        return f"Error Analysis:\n{summary}"

    return f"Unknown action '{action}' for code_project_helper."
