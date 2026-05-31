from __future__ import annotations

from resprint.frontend.i18n.fr import TRANSLATIONS


def t(key: str, **params: object) -> str:
    template = TRANSLATIONS.get(key, key)
    if not params:
        return template
    return template.format(**params)
