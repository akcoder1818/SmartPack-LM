"""
SmartPack-LM: Centralized Multilingual Translation Engine
Manages localization for English, Hindi, Tamil, Kannada, Telugu, and Malayalam across UI and PDF reports.
"""
import os
import json

TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "translations")

SUPPORTED_LANGUAGES = {
    "en": {"code": "en", "name": "English", "native": "English"},
    "hi": {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    "ta": {"code": "ta", "name": "Tamil", "native": "தமிழ்"},
    "kn": {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ"},
    "te": {"code": "te", "name": "Telugu", "native": "తెలుగు"},
    "ml": {"code": "ml", "name": "Malayalam", "native": "മലയാളം"},
    "mr": {"code": "mr", "name": "Marathi", "native": "मराठी"}
}

_TRANSLATIONS_CACHE = {}

def load_translations(lang_code="en"):
    """Loads and caches translation dictionary for a given language code."""
    if lang_code in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[lang_code]
    
    file_path = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")
    if not os.path.exists(file_path):
        # Fallback to English if file doesn't exist
        file_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _TRANSLATIONS_CACHE[lang_code] = data
            return data
    except Exception as e:
        print(f"Error loading translations for {lang_code}: {e}")
        return {}

def t(key, lang="en", default=None, **kwargs):
    """
    Translates a key into the target language with automatic English fallback.
    Supports kwargs formatting: e.g. t('welcome_msg', name='Officer')
    """
    if not lang or lang not in SUPPORTED_LANGUAGES:
        lang = "en"
        
    catalog = load_translations(lang)
    val = catalog.get(key)
    
    if val is None and lang != "en":
        # Fallback to English
        en_catalog = load_translations("en")
        val = en_catalog.get(key)
        
    if val is None:
        val = default if default is not None else key
        
    if kwargs and isinstance(val, str):
        try:
            return val.format(**kwargs)
        except Exception:
            return val
            
    return val

def get_supported_languages():
    """Returns list of supported language dictionaries."""
    return list(SUPPORTED_LANGUAGES.values())

def get_translated_status(status_str, lang="en"):
    """Translates compliance status strings."""
    status_map = {
        "COMPLIANT": "status_compliant",
        "NEEDS REVIEW": "status_needs_review",
        "NON-COMPLIANT": "status_non_compliant"
    }
    key = status_map.get(status_str, status_str)
    return t(key, lang=lang, default=status_str)

def get_translated_badge(badge_str, lang="en"):
    """Translates audit badges (PASS, REVIEW, FAIL)."""
    badge_map = {
        "PASS": "badge_pass",
        "REVIEW": "badge_review",
        "FAIL": "badge_fail"
    }
    key = badge_map.get(badge_str, badge_str)
    return t(key, lang=lang, default=badge_str)
