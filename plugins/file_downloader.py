"""
plugins/file_downloader.py — Safe File Downloader with Undo & Executable Confirmation for Charlie.

Downloads files from a URL into the user's Downloads or specified directory.
Registers file deletion with core/undo.py so downloads can be undone.
Gates executable file downloads behind core/confirm.py.
"""
from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
import requests

from core import confirm
from core import undo
from core.logger import get_logger

logger = get_logger("file_downloader")

DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads"
DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".vbs", ".msi", ".dll", ".scr"}


def _do_download(url: str, dest_path: Path) -> str:
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, stream=True, timeout=30.0)
        resp.raise_for_status()

        total_bytes = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)

        # Register undo (removes the downloaded file)
        def _undo_download():
            try:
                if dest_path.exists():
                    dest_path.unlink()
                return f"Removed downloaded file '{dest_path.name}'."
            except Exception as e:
                return f"Failed to undo download: {e}"

        undo.push_undo(f"Download {dest_path.name}", _undo_download)
        size_kb = total_bytes / 1024.0
        return f"Successfully downloaded '{dest_path.name}' ({size_kb:.1f} KB) to {dest_path.parent}."
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return f"Failed to download from {url}: {e}"


PLUGIN = {
    "name": "file_downloader",
    "description": (
        "Download a file from any URL into a destination folder. "
        "Use when the user gives a link and asks to download or save it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "The URL of the file to download"},
            "destination_folder": {"type": "STRING", "description": "Optional folder to save into (defaults to Downloads)"},
            "custom_filename": {"type": "STRING", "description": "Optional custom filename to save as"},
        },
        "required": ["url"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    url = str(parameters.get("url", "")).strip()
    dest_folder_str = str(parameters.get("destination_folder", "")).strip()
    custom_name = str(parameters.get("custom_filename", "")).strip()

    if not url:
        return "Please provide a valid download URL."

    # Parse filename from URL or custom name
    parsed = urllib.parse.urlparse(url)
    filename = custom_name or Path(parsed.path).name or "downloaded_file"

    target_dir = Path(dest_folder_str).resolve() if dest_folder_str else DEFAULT_DOWNLOAD_DIR
    target_path = target_dir / filename

    # Safety check: executable file -> require UI confirmation
    ext = target_path.suffix.lower()
    if ext in DANGEROUS_EXTENSIONS:
        logger.warning(f"Executable download '{target_path.name}' requires confirmation.")
        return confirm.request(
            key=f"dl_{filename}",
            title="Approve Executable Download",
            detail=(
                f"Charlie is requested to download an executable file:\n\n"
                f"File: {filename}\nSource: {url}\nDestination: {target_dir}\n\n"
                f"Executable files can execute arbitrary code. Approve download?"
            ),
            run=lambda: _do_download(url, target_path),
        )

    res = _do_download(url, target_path)
    if player:
        player.write_log(f"Charlie: {res}")
    return res
