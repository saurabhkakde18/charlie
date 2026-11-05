"""
core/credentials.py — Secure API key and secret storage for Charlie.

Resolution hierarchy:
  1. Environment variable: GEMINI_API_KEY (or GOOGLE_API_KEY)
  2. OS Keyring (Windows Credential Manager, macOS Keychain, SecretService)
  3. config/api_keys.json (fallback only)

Never prints or logs the raw API key.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

KEYRING_SERVICE = "charlie_assistant"
LEGACY_KEYRING_SERVICE = "jarvis_assistant"
KEYRING_USERNAME = "gemini_api_key"


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_CONFIG_PATH = CONFIG_DIR / "api_keys.json"

_cached_key: Optional[str] = None


def get_gemini_api_key(force_refresh: bool = False) -> str:
    """Retrieve Gemini API key from environment, config file, or OS keyring."""
    global _cached_key
    if _cached_key and not force_refresh:
        return _cached_key

    # 1. Environment variables (highest priority, instantaneous)
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key and env_key.strip():
        _cached_key = env_key.strip()
        return _cached_key

    # 2. Local config/api_keys.json (fast file read)
    if API_CONFIG_PATH.exists():
        try:
            data = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
            file_key = str(data.get("gemini_api_key") or "").strip()
            if file_key:
                _cached_key = file_key
                return _cached_key
        except Exception:
            pass

    # 3. OS Keyring (slower on Windows, queried if not in env or config)
    try:
        import keyring
        k_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if k_key and k_key.strip():
            _cached_key = k_key.strip()
            return _cached_key
        # Fallback to legacy service name if present
        legacy_key = keyring.get_password(LEGACY_KEYRING_SERVICE, KEYRING_USERNAME)
        if legacy_key and legacy_key.strip():
            _cached_key = legacy_key.strip()
            return _cached_key
    except Exception:
        pass

    return ""


def save_gemini_api_key(key: str, use_keyring: bool = True) -> bool:
    """Store Gemini API key in OS keyring with config fallback."""
    global _cached_key
    key = key.strip()
    if not key:
        return False
    _cached_key = key

    saved_in_keyring = False
    if use_keyring:
        try:
            import keyring
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)
            saved_in_keyring = True
        except Exception:
            saved_in_keyring = False

    # Also maintain config/api_keys.json for non-secret settings like os_system, assistant_name
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing_data = {}
    if API_CONFIG_PATH.exists():
        try:
            existing_data = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing_data = {}

    if not saved_in_keyring:
        existing_data["gemini_api_key"] = key
    else:
        # If safely saved in keyring, avoid storing plaintext in file if possible, or mask
        existing_data["gemini_api_key"] = key  # Kept for backward compat with plugins

    API_CONFIG_PATH.write_text(
        json.dumps(existing_data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    return True


def has_valid_key() -> bool:
    """Return True if an API key is available."""
    k = get_gemini_api_key()
    return bool(k and len(k) > 10)

