from __future__ import annotations

from importlib.resources import files

from resprint.frontend.utils.templates import render_template


def common_css() -> str:
    return static_text("common.css")


def static_text(filename: str) -> str:
    return (
        files("resprint.frontend.static").joinpath(filename).read_text(encoding="utf-8")
    )


def render_page(
    title: str,
    content: str,
    *,
    header_actions: str = "",
    extra_css: str = "",
    scripts: str = "",
    max_width: str = "1180px",
) -> str:
    return render_template(
        "base.html",
        title=title,
        content=content,
        header_actions=header_actions,
        common_css=common_css(),
        extra_css=extra_css,
        max_width=max_width,
        theme_script=static_text("theme.js"),
        scripts=scripts,
    )
