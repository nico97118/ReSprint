from __future__ import annotations

import json
from dataclasses import asdict

from resprint.models import Sprint, SprintReview
from resprint.presentation.report import _item_to_json


def render_json(review: SprintReview, sprint: Sprint) -> str:
    payload = {
        "sprint": asdict(sprint),
        "completed": [_item_to_json(item) for item in review.completed],
        "unfinished_with_time": [
            _item_to_json(item) for item in review.unfinished_with_time
        ],
        "not_started": [_item_to_json(item) for item in review.not_started],
    }
    return json.dumps(payload, default=str, indent=2, ensure_ascii=False) + "\n"
