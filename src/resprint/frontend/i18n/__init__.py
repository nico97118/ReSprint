from __future__ import annotations

from functools import cache
from importlib import import_module

DEFAULT_LANGUAGE = "fr"
SUPPORTED_LANGUAGES = ("fr", "en")

_current_language = DEFAULT_LANGUAGE


def configure_language(language: str | None) -> str:
    global _current_language
    _current_language = normalize_language(language)
    return _current_language


def current_language() -> str:
    return _current_language


def normalize_language(language: str | None) -> str:
    normalized = (language or DEFAULT_LANGUAGE).strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise ValueError(
            f"Unsupported frontend language '{language}'. Expected: {supported}"
        )
    return normalized


@cache
def _catalog(language: str) -> dict[str, str]:
    module = import_module(f"{__name__}.{normalize_language(language)}")
    return dict(module.TRANSLATIONS)


def t(key: str, **params: object) -> str:
    template = _catalog(_current_language).get(key, key)
    if not params:
        return template
    return template.format(**params)
