from __future__ import annotations

import json
from dataclasses import asdict

from resprint.exporters.common import item_to_json
from resprint.logging import get_logger
from resprint.models import Sprint, SprintReview

logger = get_logger(__name__)


def render_json(
    review: SprintReview,
    sprint: Sprint,
    jql: str | None = None,
) -> str:
    logger.info("Rendering JSON report for sprint %s", sprint.name)
    payload = {
        "sprint": asdict(sprint),
        "completed": [item_to_json(item) for item in review.completed],
        "unfinished_with_time": [
            item_to_json(item) for item in review.unfinished_with_time
        ],
        "not_started": [item_to_json(item) for item in review.not_started],
        "out_of_sprint": [item_to_json(item) for item in review.out_of_sprint],
    }
    if jql:
        logger.debug("Including JQL in JSON export")
        payload["jql"] = jql
    logger.debug(
        "JSON report sections completed=%s unfinished=%s "
        "not_started=%s out_of_sprint=%s",
        len(review.completed),
        len(review.unfinished_with_time),
        len(review.not_started),
        len(review.out_of_sprint),
    )
    return json.dumps(payload, default=str, indent=2, ensure_ascii=False) + "\n"
