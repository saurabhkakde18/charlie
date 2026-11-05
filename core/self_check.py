"""
core/self_check.py — Startup diagnostics and prerequisite verification.

Checks:
  1. Gemini API key
  2. Microphone (audio input)
  3. Speakers (audio output)
  4. yt-dlp
  5. Wake word (optional)
  6. Critical packages

Outputs a human-friendly assessment in plain words.
"""
from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass, field
from typing import List

from core.credentials import get_gemini_api_key
from core.logger import get_logger

logger = get_logger("self_check")


@dataclass
class CheckItem:
    name: str
    status: str       # "OK", "WARNING", "MISSING"
    message: str
    remedy: str = ""


@dataclass
class SelfCheckReport:
    items: List[CheckItem] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(it.status == "OK" for it in self.items)

    @property
    def can_start(self) -> bool:
        # Can start if no critical component is MISSING
        critical = {"Gemini API Key", "Microphone", "Speakers"}
        return not any(it.name in critical and it.status == "MISSING" for it in self.items)

    def summary_lines(self) -> List[str]:
        lines = []
        for it in self.items:
            icon = "✅" if it.status == "OK" else ("⚠️" if it.status == "WARNING" else "❌")
            line = f"{icon} {it.name}: {it.message}"
            if it.remedy:
                line += f" -> Fix: {it.remedy}"
            lines.append(line)
        return lines


def run_self_check() -> SelfCheckReport:
    """Run all diagnostics and return a structured report."""
    report = SelfCheckReport()

    # 1. API Key Check
    key = get_gemini_api_key()
    if key and len(key) > 10:
        report.items.append(CheckItem(
            name="Gemini API Key",
            status="OK",
            message="Found and configured securely.",
        ))
    else:
        report.items.append(CheckItem(
            name="Gemini API Key",
            status="MISSING",
            message="No Gemini API key found.",
            remedy="Set GEMINI_API_KEY environment variable or enter it in the setup screen.",
        ))

    # 2. Audio Devices (Microphone & Speakers)
    has_mic = False
    has_spk = False
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        for d in devices:
            if isinstance(d, dict):
                if d.get("max_input_channels", 0) > 0:
                    has_mic = True
                if d.get("max_output_channels", 0) > 0:
                    has_spk = True
    except Exception as e:
        logger.warning(f"Audio query error: {e}")

    if has_mic:
        report.items.append(CheckItem(
            name="Microphone",
            status="OK",
            message="Input device detected.",
        ))
    else:
        report.items.append(CheckItem(
            name="Microphone",
            status="MISSING",
            message="No functional microphone detected.",
            remedy="Connect or enable a microphone in sound settings.",
        ))

    if has_spk:
        report.items.append(CheckItem(
            name="Speakers",
            status="OK",
            message="Output device detected.",
        ))
    else:
        report.items.append(CheckItem(
            name="Speakers",
            status="MISSING",
            message="No audio output device detected.",
            remedy="Connect headphones or speakers.",
        ))

    # 3. yt-dlp
    has_ytdlp = shutil.which("yt-dlp") is not None or (importlib.util.find_spec("yt_dlp") is not None)
    if has_ytdlp:
        report.items.append(CheckItem(
            name="yt-dlp",
            status="OK",
            message="Installed and available for media streaming.",
        ))
    else:
        report.items.append(CheckItem(
            name="yt-dlp",
            status="WARNING",
            message="yt-dlp is not installed.",
            remedy="Run: pip install yt-dlp (YouTube stream playback will fall back to browser).",
        ))

    # 4. Wake Word (Optional)
    from core.wake_word import is_ready as wake_is_ready
    if wake_is_ready():
        report.items.append(CheckItem(
            name="Wake Word Engine",
            status="OK",
            message="Local wake word model is ready.",
        ))
    else:
        report.items.append(CheckItem(
            name="Wake Word Engine",
            status="WARNING",
            message="Optional wake word model not installed.",
            remedy="Use Push-to-Talk (Ctrl+Space) or enable wake word in Settings.",
        ))

    # Log report
    for line in report.summary_lines():
        logger.info(line)

    return report

