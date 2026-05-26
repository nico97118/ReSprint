from __future__ import annotations

import html


def html_text(value: object) -> str:
    return html.escape(str(value), quote=False)


def html_attr(value: object) -> str:
    return html.escape(str(value), quote=True)
