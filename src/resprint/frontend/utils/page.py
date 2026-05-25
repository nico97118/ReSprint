from __future__ import annotations

from importlib.resources import files

from resprint.frontend.utils.templates import render_template


def common_css() -> str:
    return static_text("common.css")


def static_text(filename: str) -> str:
    return (
        files("resprint.frontend.static").joinpath(filename).read_text(encoding="utf-8")
    )


def asset_url(filename: str) -> str:
    return f"/assets/{filename}"


def vendor_script(filename: str) -> str:
    return f'<script src="{asset_url(f"vendor/{filename}")}"></script>'


def render_page(
    title: str,
    content: str,
    *,
    header_actions: str = "",
    extra_css: str = "",
    vendor_scripts: str = "",
    scripts: str = "",
    max_width: str = "1180px",
) -> str:
    return render_template(
        "base.html",
        title=title,
        content=content,
        header_actions=header_actions,
        mdi_stylesheet_url=asset_url("vendor/mdi/css/materialdesignicons.min.css"),
        common_css=common_css(),
        extra_css=extra_css,
        vendor_scripts=vendor_scripts,
        max_width=max_width,
        theme_script=static_text("theme.js"),
        scripts=scripts,
    )
