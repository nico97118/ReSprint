from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, PackageLoader, select_autoescape

from resprint.frontend.i18n import t


@lru_cache
def _environment() -> Environment:
    return Environment(
        loader=PackageLoader("resprint.frontend", "templates"),
        autoescape=select_autoescape(("html",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(template_name: str, **context: object) -> str:
    return _environment().get_template(template_name).render(t=t, **context)
