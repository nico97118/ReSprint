from __future__ import annotations

import json
from typing import Any

from markupsafe import escape


def render_chart(
    chart_id: str,
    config: dict[str, Any],
    *,
    label: str,
    class_name: str = "chart-canvas",
) -> str:
    return (
        f'<canvas id="{escape(chart_id)}" class="{escape(class_name)}" '
        f'role="img" aria-label="{escape(label)}" '
        f"data-chart-config='{_chart_config(config)}'></canvas>"
    )


def _chart_config(config: dict[str, Any]) -> str:
    return escape(
        json.dumps(
            config,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
