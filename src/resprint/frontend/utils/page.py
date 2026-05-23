from __future__ import annotations

from importlib.resources import files

from resprint.frontend.utils.templates import render_template

THEME_INIT_SCRIPT = """(function () {
      let theme = "light";
      try {
        theme = localStorage.getItem("resprint-theme") || theme;
      } catch (_error) {
        theme = "light";
      }
      document.documentElement.setAttribute("data-theme", theme);
    })();"""

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
    return static_text("common.css")


def static_text(filename: str) -> str:
    return (
        files("resprint.frontend.static").joinpath(filename).read_text(encoding="utf-8")
    )


def render_page(
    title: str,
    content: str,
    *,
    extra_css: str = "",
    scripts: str = "",
    max_width: str = "1180px",
) -> str:
    return render_template(
        "base.html",
        title=title,
        content=content,
        common_css=common_css(),
        extra_css=extra_css,
        max_width=max_width,
        theme_init_script=THEME_INIT_SCRIPT,
        theme_script=THEME_SCRIPT,
        scripts=scripts,
    )
