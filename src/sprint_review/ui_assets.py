from __future__ import annotations

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
        theme = localStorage.getItem("sprint-review-theme") || theme;
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
          localStorage.setItem("sprint-review-theme", theme);
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
            ? "mdi mdi-moon-waning-crescent"
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
        files("sprint_review.static").joinpath("common.css").read_text(encoding="utf-8")
    )


def ui_context() -> dict[str, str]:
    return {
        "common_css": common_css(),
        "mdi_stylesheet": MDI_STYLESHEET,
        "theme_init_script": THEME_INIT_SCRIPT,
        "theme_script": THEME_SCRIPT,
        "theme_switch": THEME_SWITCH,
    }
