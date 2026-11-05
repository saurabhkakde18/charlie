"""
tests/test_i18n.py — Unit tests for the i18n translation and override layer.
"""
from __future__ import annotations

from core import i18n


def test_i18n_fallback():
    # Known key in English
    assert i18n.t("status_listening", lang="en") == "LISTENING"

    # Known key in Spanish
    assert i18n.t("status_listening", lang="es") == "ESCUCHANDO"

    # Unknown language code should fall back cleanly to English
    assert i18n.t("status_listening", lang="xx") == "LISTENING"

    # Unknown key should return the default parameter or the key itself
    assert i18n.t("non_existent_key", default="Default Val") == "Default Val"
    assert i18n.t("non_existent_key") == "non_existent_key"


def test_i18n_interpolation():
    msg = i18n.t("tool_error", lang="en", tool_name="search", error="timeout")
    assert "search" in msg and "timeout" in msg


def test_language_override_detection():
    # English
    r1 = i18n.detect_language_override("Please speak English now")
    assert r1 is not None and r1[0] == "en"

    # Hindi
    r2 = i18n.detect_language_override("हिंदी में बात करो")
    assert r2 is not None and r2[0] == "hi"

    # Spanish
    r3 = i18n.detect_language_override("por favor habla español")
    assert r3 is not None and r3[0] == "es"

    # Turkish
    r4 = i18n.detect_language_override("Türkçe konuş")
    assert r4 is not None and r4[0] == "tr"

    # Non-override phrase should return None
    assert i18n.detect_language_override("What time is it in Paris?") is None
