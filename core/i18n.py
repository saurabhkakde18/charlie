"""
core/i18n.py — Lightweight Internationalization and Language Adaptation Layer for Charlie.

Capabilities:
  • Multi-language dictionary for HUD states, notifications, and error wrappers.
  • Silent language detection tracking and explicit override detection ("speak <language>").
  • Language normalization and mapping across ISO codes and localized names.
  • Degradation and fallback safety: never raises KeyError, falls back to English.
"""
from __future__ import annotations

import re
from typing import Optional, Dict, Any

from core.logger import get_logger

logger = get_logger("i18n")

# Default language
DEFAULT_LANGUAGE = "en"

# Common UI strings and status translations
_STRINGS: Dict[str, Dict[str, str]] = {
    "status_listening": {
        "en": "LISTENING",
        "hi": "सुन रहा हूँ",
        "mr": "ऐकत आहे",
        "tr": "DİNLİYOR",
        "ar": "استماع",
        "es": "ESCUCHANDO",
        "ja": "聞いています",
    },
    "status_thinking": {
        "en": "THINKING",
        "hi": "सोच रहा हूँ",
        "mr": "विचार करत आहे",
        "tr": "DÜŞÜNÜYOR",
        "ar": "تفكير",
        "es": "PENSANDO",
        "ja": "考えています",
    },
    "status_speaking": {
        "en": "SPEAKING",
        "hi": "बोल रहा हूँ",
        "mr": "बोलत आहे",
        "tr": "KONUŞUYOR",
        "ar": "تحدث",
        "es": "HABLANDO",
        "ja": "話しています",
    },
    "status_asleep": {
        "en": "ASLEEP",
        "hi": "निष्क्रिय",
        "mr": "झोपलेला",
        "tr": "UYKUDA",
        "ar": "خامل",
        "es": "EN ESPERA",
        "ja": "待機中",
    },
    "status_muted": {
        "en": "MUTED",
        "hi": "मौन",
        "mr": "म्यूट",
        "tr": "SESSİZ",
        "ar": "مكتوم",
        "es": "SILENCIADO",
        "ja": "消音",
    },
    "confirm_required": {
        "en": "Action requires your confirmation on screen.",
        "hi": "इस क्रिया के लिए स्क्रीन पर आपकी पुष्टि की आवश्यकता है।",
        "mr": "या कृतीसाठी स्क्रीनवर आपल्या मंजुरीची आवश्यकता आहे.",
        "tr": "Bu işlem ekranda onayınızı gerektiriyor.",
        "ar": "يتطلب هذا الإجراء تأكيدك على الشاشة.",
        "es": "Esta acción requiere su confirmación en pantalla.",
        "ja": "この操作には画面での確認が必要です。",
    },
    "tool_error": {
        "en": "I encountered an issue executing {tool_name}: {error}",
        "hi": "{tool_name} निष्पादित करते समय त्रुटि आई: {error}",
        "mr": "{tool_name} कार्यान्वित करताना त्रुटी आली: {error}",
        "tr": "{tool_name} çalıştırılırken bir sorun oluştu: {error}",
        "ar": "حدث خطأ أثناء تنفيذ {tool_name}: {error}",
        "es": "Ocurrió un problema al ejecutar {tool_name}: {error}",
        "ja": "{tool_name} の実行中にエラーが発生しました: {error}",
    },
    "language_switched": {
        "en": "Switched language to {language}.",
        "hi": "भाषा बदलकर {language} कर दी गई है।",
        "mr": "भाषा बदलून {language} केली आहे.",
        "tr": "Dil {language} olarak değiştirildi.",
        "ar": "تم تغيير اللغة إلى {language}.",
        "es": "Idioma cambiado a {language}.",
        "ja": "言語を {language} に切り替えました。",
    },
}

# Mapping of language names in multiple languages to standardized language code and display name
_LANGUAGE_MAP: Dict[str, tuple[str, str]] = {
    # English
    "english": ("en", "English"),
    "en": ("en", "English"),
    "अंग्रेजी": ("en", "English"),
    "इंग्रजी": ("en", "English"),
    "İngilizce": ("en", "English"),
    "ingilizce": ("en", "English"),
    "inglés": ("en", "English"),
    "ingles": ("en", "English"),
    "英語": ("en", "English"),
    # Hindi
    "hindi": ("hi", "Hindi"),
    "hi": ("hi", "Hindi"),
    "हिंदी": ("hi", "Hindi"),
    "हिन्दी": ("hi", "Hindi"),
    "hintçe": ("hi", "Hindi"),
    "hindú": ("hi", "Hindi"),
    "ヒンディー語": ("hi", "Hindi"),
    # Marathi
    "marathi": ("mr", "Marathi"),
    "mr": ("mr", "Marathi"),
    "मराठी": ("mr", "Marathi"),
    "मराठीत": ("mr", "Marathi"),
    "maratice": ("mr", "Marathi"),
    "マラティー語": ("mr", "Marathi"),
    # Turkish
    "turkish": ("tr", "Turkish"),
    "tr": ("tr", "Turkish"),
    "türkçe": ("tr", "Turkish"),
    "turkce": ("tr", "Turkish"),
    "तुर्की": ("tr", "Turkish"),
    "turco": ("tr", "Turkish"),
    "トルコ語": ("tr", "Turkish"),
    # Arabic
    "arabic": ("ar", "Arabic"),
    "ar": ("ar", "Arabic"),
    "عربي": ("ar", "Arabic"),
    "عربية": ("ar", "Arabic"),
    "العربية": ("ar", "Arabic"),
    "بالعربية": ("ar", "Arabic"),
    "بالعربي": ("ar", "Arabic"),
    "अरबी": ("ar", "Arabic"),
    "arapça": ("ar", "Arabic"),
    "árabe": ("ar", "Arabic"),
    "arabe": ("ar", "Arabic"),
    "アラビア語": ("ar", "Arabic"),
    # Spanish
    "spanish": ("es", "Spanish"),
    "es": ("es", "Spanish"),
    "español": ("es", "Spanish"),
    "espanol": ("es", "Spanish"),
    "स्पैनिश": ("es", "Spanish"),
    "ispanyolca": ("es", "Spanish"),
    "スペイン語": ("es", "Spanish"),
    # Japanese
    "japanese": ("ja", "Japanese"),
    "ja": ("ja", "Japanese"),
    "日本語": ("ja", "Japanese"),
    "जापानी": ("ja", "Japanese"),
    "japonca": ("ja", "Japanese"),
    "japonés": ("ja", "Japanese"),
    "japones": ("ja", "Japanese"),
    # German
    "german": ("de", "German"),
    "deutsch": ("de", "German"),
    "जर्मन": ("de", "German"),
    "almanca": ("de", "German"),
    "alemán": ("de", "German"),
    "aleman": ("de", "German"),
    "ドイツ語": ("de", "German"),
    # French
    "french": ("fr", "French"),
    "français": ("fr", "French"),
    "francais": ("fr", "French"),
    "फ्रेंच": ("fr", "French"),
    "fransızca": ("fr", "French"),
    "francés": ("fr", "French"),
    "frances": ("fr", "French"),
    "フランス語": ("fr", "French"),
}

# Regex patterns to detect explicit user request to switch language
_OVERRIDE_PATTERNS = [
    re.compile(r"(?:speak|switch to|talk in|reply in|change language to)\s+([a-zA-Z\u00C0-\u024F\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u4E00-\u9FFF]+)", re.IGNORECASE),
    re.compile(r"([a-zA-Z\u00C0-\u024F\u0900-\u097F]+)\s+(?:में बात करो|में बोलो|भाषा चुनो)", re.IGNORECASE),
    re.compile(r"([a-zA-Z\u00C0-\u024F\u0900-\u097F]+)(?:त|मध्ये)?\s+(?:बोला|संवाद साधा)", re.IGNORECASE),
    re.compile(r"([a-zA-Z\u00C0-\u024F]+)\s+(?:konuş|konuşalım|diline geç)", re.IGNORECASE),
    re.compile(r"(?:habla|cambia al|responde en)\s+([a-zA-Z\u00C0-\u024F]+)", re.IGNORECASE),
    re.compile(r"(?:تحدث|تكلم)\s+(?:بال|بـ|ب)?([a-zA-Z\u0600-\u06FF]+)", re.IGNORECASE),
    re.compile(r"([a-zA-Z\u3040-\u30FF\u4E00-\u9FFF]+)\s*(?:で話して|で答えて)", re.IGNORECASE),
]

_active_language: str = DEFAULT_LANGUAGE


def set_active_language(lang_code_or_name: str) -> str:
    """Set the active language code. Returns the resolved code (e.g., 'en', 'hi')."""
    global _active_language
    norm = lang_code_or_name.strip().lower()
    if norm in _LANGUAGE_MAP:
        _active_language = _LANGUAGE_MAP[norm][0]
    else:
        # Check by prefix or leave as 2-letter code if valid
        if len(norm) == 2 and norm.isalpha():
            _active_language = norm
        else:
            _active_language = DEFAULT_LANGUAGE
    logger.info(f"Active language set to: {_active_language}")
    return _active_language


def get_active_language() -> str:
    """Return the active 2-letter language code."""
    return _active_language


def detect_language_override(user_text: str) -> Optional[tuple[str, str]]:
    """
    Check if the user input explicitly asks to switch language.
    Returns (code, display_name), e.g. ('hi', 'Hindi'), or None.
    """
    if not user_text:
        return None

    text = user_text.strip()
    for pat in _OVERRIDE_PATTERNS:
        m = pat.search(text)
        if m:
            target = m.group(1).strip().lower()
            if target in _LANGUAGE_MAP:
                return _LANGUAGE_MAP[target]
            # Try fuzzy check in map keys
            for key, val in _LANGUAGE_MAP.items():
                if key.lower() == target or target == key.lower():
                    return val

    # Direct short command e.g. "speak Hindi" or "Hindi please"
    words = text.lower().split()
    if len(words) <= 3:
        for w in words:
            clean = re.sub(r"[^\w]", "", w)
            if clean in _LANGUAGE_MAP:
                return _LANGUAGE_MAP[clean]

    return None


def t(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Lookup a localized string with parameter interpolation and fallback to English.
    """
    target_lang = lang or _active_language
    item = _STRINGS.get(key)
    if not item:
        return kwargs.get("default", key)

    text = item.get(target_lang) or item.get("en") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
