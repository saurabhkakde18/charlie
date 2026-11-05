"""
plugins/media_control.py — Cross-Platform Media and Volume Control for Charlie.

Controls system playback (play/pause, next, previous) and volume level.
Registers volume adjustments with core/undo.py.
"""
from __future__ import annotations

import os
import platform
import subprocess

from core import undo
from core.logger import get_logger

logger = get_logger("media_control")
OS = platform.system()


def _press_key(key: str) -> bool:
    try:
        import pyautogui
        pyautogui.press(key)
        return True
    except Exception:
        return False


def _set_volume_windows(percent: int) -> bool:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        # percent [0, 100] -> scalar [0.0, 1.0]
        scalar = max(0.0, min(1.0, percent / 100.0))
        vol.SetMasterVolumeLevelScalar(scalar, None)
        return True
    except Exception as e:
        logger.error(f"Failed to set volume on Windows: {e}")
        return False


def _get_volume_windows() -> int:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        return int(round(vol.GetMasterVolumeLevelScalar() * 100))
    except Exception:
        return 50


PLUGIN = {
    "name": "media_control",
    "description": (
        "Control media playback and system volume. "
        "Supports play/pause, next track, previous track, mute, unmute, and setting volume percentage."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: 'play_pause', 'next', 'previous', 'volume_up', 'volume_down', 'set_volume', 'mute', 'unmute'",
            },
            "volume_percent": {
                "type": "INTEGER",
                "description": "Target volume percentage from 0 to 100 (for 'set_volume')",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip().lower()
    target_vol = parameters.get("volume_percent")

    if action in ("play_pause", "play", "pause"):
        if OS == "Windows":
            _press_key("playpause")
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 16 using {command down}'], check=False)
        else:
            subprocess.run(["playerctl", "play-pause"], check=False)
        return "Toggled media playback."

    elif action == "next":
        if OS == "Windows":
            _press_key("nexttrack")
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", 'tell application "Music" to next track'], check=False)
        else:
            subprocess.run(["playerctl", "next"], check=False)
        return "Skipped to next track."

    elif action == "previous":
        if OS == "Windows":
            _press_key("prevtrack")
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", 'tell application "Music" to previous track'], check=False)
        else:
            subprocess.run(["playerctl", "previous"], check=False)
        return "Returned to previous track."

    elif action == "mute":
        if OS == "Windows":
            _press_key("volumemute")
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", "set volume with output muted"], check=False)
        else:
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], check=False)
        return "Muted system audio."

    elif action == "unmute":
        if OS == "Windows":
            _press_key("volumemute")
        elif OS == "Darwin":
            subprocess.run(["osascript", "-e", "set volume without output muted"], check=False)
        else:
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], check=False)
        return "Unmuted system audio."

    elif action in ("set_volume", "volume_up", "volume_down"):
        old_vol = _get_volume_windows() if OS == "Windows" else 50

        if action == "volume_up":
            new_vol = min(100, old_vol + 10)
        elif action == "volume_down":
            new_vol = max(0, old_vol - 10)
        else:
            if target_vol is None:
                return "Please specify volume_percent between 0 and 100."
            new_vol = max(0, min(100, int(target_vol)))

        success = False
        if OS == "Windows":
            success = _set_volume_windows(new_vol)
        elif OS == "Darwin":
            res = subprocess.run(["osascript", "-e", f"set volume output volume {new_vol}"], check=False)
            success = (res.returncode == 0)
        else:
            res = subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{new_vol}%"], check=False)
            success = (res.returncode == 0)

        if success:
            def _undo_vol():
                if OS == "Windows":
                    _set_volume_windows(old_vol)
                elif OS == "Darwin":
                    subprocess.run(["osascript", "-e", f"set volume output volume {old_vol}"], check=False)
                else:
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{old_vol}%"], check=False)
                return f"Restored volume to {old_vol}%."

            undo.push_undo(f"Volume → {new_vol}%", _undo_vol)
            return f"Set volume to {new_vol}%."
        return f"Failed to set volume to {new_vol}%."

    return f"Unknown media action '{action}'."

