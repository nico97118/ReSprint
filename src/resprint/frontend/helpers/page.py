from __future__ import annotations

import html
from importlib.resources import files

MDI_STYLESHEET = """<link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css"
  >"""

THEME_SWITCH = """<button
      class="theme-switch"
      type="button"
      aria-label="Changer le theme"
      role="switch"
      aria-checked="false"
      data-theme-toggle
    >
      <span class="theme-switch-thumb">
        <span class="mdi mdi-weather-sunny" aria-hidden="true" data-theme-icon></span>
      </span>
    </button>"""

THEME_INIT_SCRIPT = """<script>
    (function () {
      let theme = "light";
      try {
        theme = localStorage.getItem("resprint-theme") || theme;
      } catch (_error) {
        theme = "light";
      }
      document.documentElement.setAttribute("data-theme", theme);
    })();
  </script>"""

THEME_SCRIPT = """(function () {
      const themeToggle = document.querySelector("[data-theme-toggle]");
      const themeIcon = document.querySelector("[data-theme-icon]");

      function currentTheme() {
        return document.documentElement.getAttribute("data-theme") === "dark"
          ? "dark"
          : "light";
      }

      function persistTheme(theme) {
        try {
          localStorage.setItem("resprint-theme", theme);
        } catch (_error) {
          return;
        }
      }

      function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        persistTheme(theme);
        if (themeToggle) {
          themeToggle.setAttribute("aria-checked", String(theme === "dark"));
        }
        if (themeIcon) {
          themeIcon.className = theme === "dark"
            ? "mdi mdi-weather-night"
            : "mdi mdi-weather-sunny";
        }
      }

      applyTheme(currentTheme());
      if (themeToggle) {
        themeToggle.addEventListener("click", () => {
          applyTheme(currentTheme() === "dark" ? "light" : "dark");
        });
      }
    })();"""


def common_css() -> str:
    return (
        files("resprint.frontend.static")
        .joinpath("common.css")
        .read_text(encoding="utf-8")
    )


def render_page(
    title: str,
    content: str,
    *,
    extra_css: str = "",
    scripts: str = "",
    max_width: str = "1180px",
) -> str:
    escaped_title = html.escape(title, quote=False)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  {MDI_STYLESHEET}
  <style>
    {common_css()}
    main {{ max-width: {html.escape(max_width, quote=True)}; }}
    .page-header {{ margin-bottom: 20px; }}
    .page-header h1 {{ margin: 0; }}
    .page-footer {{
      margin-top: 48px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
    }}
    {extra_css}
  </style>
  {THEME_INIT_SCRIPT}
</head>
<body>
  <main>
    {THEME_SWITCH}
    <header class="page-header">
      <h1>{escaped_title}</h1>
    </header>
    {content}
    <footer class="page-footer">ReSprint</footer>
  </main>
  <script>
    {THEME_SCRIPT}
    {scripts}
  </script>
</body>
</html>"""
