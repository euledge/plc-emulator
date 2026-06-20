import json
import os


_TRANSLATIONS: dict[str, dict] = {}


def load_translations() -> None:
    base = os.path.dirname(__file__)
    for lang in ("ja", "en"):
        path = os.path.join(base, f"{lang}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                _TRANSLATIONS[lang] = json.load(f)


def get_translation(lang: str) -> dict:
    if not _TRANSLATIONS:
        load_translations()
    return _TRANSLATIONS.get(lang, {})
