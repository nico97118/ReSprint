from __future__ import annotations

from resprint import __version__
from resprint.frontend.utils.templates import render_template


def asset_url(filename: str) -> str:
    return f"/assets/{filename}"


def render_page(
    title: str,
    content: str,
    *,
    header_actions: str = "",
    stylesheets: tuple[str, ...] = (),
    head_scripts: tuple[str, ...] = (),
    scripts: tuple[str, ...] = (),
) -> str:
    return render_template(
        "layouts/base.html",
        title=title,
        content=content,
        header_actions=header_actions,
        favicon_url=asset_url("favicon.svg"),
        mdi_stylesheet_url=asset_url("vendor/mdi/css/materialdesignicons.min.css"),
        stylesheets=stylesheets,
        head_scripts=head_scripts,
        scripts=scripts,
        app_version=__version__,
    )
