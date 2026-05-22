from __future__ import annotations

import json
from dataclasses import asdict

from resprint.exporters.common import item_to_json
from resprint.models import Sprint, SprintReview


def render_json(review: SprintReview, sprint: Sprint) -> str:
    payload = {
        "sprint": asdict(sprint),
        "completed": [item_to_json(item) for item in review.completed],
        "unfinished_with_time": [
            item_to_json(item) for item in review.unfinished_with_time
        ],
        "not_started": [item_to_json(item) for item in review.not_started],
    }
    return json.dumps(payload, default=str, indent=2, ensure_ascii=False) + "\n"
