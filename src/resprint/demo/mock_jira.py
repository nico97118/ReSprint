"""Local Jira Data Center and Tempo fixtures exercising the real HTTP clients."""

import re
from copy import deepcopy
from datetime import date

from flask import Flask, Response, abort, jsonify, request
from markupsafe import escape

from resprint.demo.data import (
    COMMENTS,
    ISSUES,
    REVIEW_FIELD,
    SPRINT,
    SPRINT_ID,
    SPRINT_KEYS,
    TEAM_ID,
    TOKEN,
    USERS,
    WORKLOGS,
)
from resprint.demo.server import run_fixture


def _page(items: list, name: str, cap: int = 2) -> dict:
    start = max(0, int(request.args.get("startAt", 0)))
    size = max(1, min(int(request.args.get("maxResults", cap)), cap))
    return dict(
        startAt=start,
        maxResults=size,
        total=len(items),
        isLast=start + size >= len(items),
        **{name: items[start : start + size]},
    )


def _search(jql: str) -> list[dict]:
    """Support explicit demo JQL clauses; reject unsupported syntax with HTTP 400."""
    source = re.sub(r"\s+ORDER\s+BY\s+key(?:\s+(?:ASC|DESC))?\s*$", "", jql, flags=re.I)
    keys = set(ISSUES)
    for clause in re.split(r"\s+AND\s+", source, flags=re.I):
        clause = clause.strip()
        if clause.startswith("(") and clause.endswith(")"):
            clause = clause[1:-1].strip()
        if re.fullmatch(r'project\s*=\s*[\'"]?ABC[\'"]?', clause, re.I):
            continue
        sprint = re.fullmatch(r"sprint\s*=\s*(\d+)", clause, re.I)
        selected = re.fullmatch(r"(?:key|issue)\s+in\s*\(([^()]*)\)", clause, re.I)
        if sprint:
            keys &= set(SPRINT_KEYS) if int(sprint[1]) == SPRINT_ID else set()
        elif selected:
            requested = {
                key.strip().strip("'\"").upper() for key in selected[1].split(",")
            }
            if not requested <= set(ISSUES):
                abort(400, description="Unknown demo issue key")
            keys &= requested
        else:
            abort(
                400,
                description=(
                    "Demo JQL supports project = ABC, sprint = 456, "
                    "key in (...) and AND"
                ),
            )
    return [
        deepcopy(ISSUES[key])
        for key in sorted(
            keys,
            key=lambda key: int(key.split("-")[1]),
            reverse=bool(re.search(r"ORDER\s+BY\s+key\s+DESC\s*$", jql, re.I)),
        )
    ]


def create_mock_jira() -> Flask:
    """Create a read-only fictional Jira/Tempo app; no external calls are made."""
    app = Flask(__name__)

    @app.before_request
    def authenticate():
        if (
            request.path.startswith("/rest/")
            and request.headers.get("Authorization") != f"Bearer {TOKEN}"
        ):
            abort(401)

    @app.get("/healthz")
    def health():
        return "ok"

    @app.get("/rest/api/<int:version>/serverInfo")
    def info(version):
        return dict(version="11.3.12", deploymentType="Server")

    @app.get("/rest/agile/1.0/board")
    def boards():
        values = [dict(id=1, name="Équipe de démonstration", type="scrum")]
        return _page(
            values if request.args.get("projectKeyOrId", "ABC") == "ABC" else [],
            "values",
        )

    @app.get("/rest/agile/1.0/board/<int:board_id>/sprint")
    def sprints(board_id):
        return _page([SPRINT] if board_id == 1 else [], "values")

    @app.get("/rest/agile/1.0/sprint/<int:sprint_id>")
    def sprint(sprint_id):
        if sprint_id != SPRINT_ID:
            abort(404)
        return SPRINT

    @app.get("/rest/api/<int:version>/search")
    def search(version):
        fields = {value for value in request.args.get("fields", "").split(",") if value}
        allowed = set().union(
            *(issue["fields"].keys() for issue in ISSUES.values())
        ) | {"key", "comment", REVIEW_FIELD, "timetracking"}
        if fields - allowed:
            abort(400, description="Unknown demo field")
        items = _search(request.args.get("jql", "project = ABC"))
        for item in items:
            item["fields"] = {
                key: value
                for key, value in item["fields"].items()
                if not fields or key in fields
            }
        return _page(items, "issues")

    def resolve(key):
        if key in ISSUES:
            return key
        for candidate, issue in ISSUES.items():
            if issue["id"] == key:
                return candidate
        abort(404)

    @app.get("/rest/api/<int:version>/issue/<key>")
    def issue(version, key):
        key = resolve(key)
        item = deepcopy(ISSUES[key])
        item["changelog"] = dict(
            startAt=0,
            maxResults=1,
            total=1,
            histories=[
                dict(
                    id="1",
                    author=USERS["alice"],
                    created="2026-11-06T11:00:00.000+0000",
                    items=[
                        dict(
                            field="status",
                            fromString="À faire",
                            toString=item["fields"]["status"]["name"],
                        )
                    ],
                )
            ],
        )
        return item

    @app.get("/rest/api/<int:version>/issue/<key>/worklog")
    def worklogs(version, key):
        return _page(WORKLOGS.get(resolve(key), []), "worklogs", 50)

    @app.get("/rest/api/<int:version>/issue/<key>/comment")
    def comments(version, key):
        return _page(COMMENTS.get(resolve(key), []), "comments")

    @app.get("/rest/api/<int:version>/user")
    def user(version):
        key = request.args.get("key") or request.args.get("username")
        if key not in USERS:
            abort(404)
        return USERS[key]

    @app.get("/rest/tempo-teams/2/team")
    def teams():
        return jsonify([dict(id=TEAM_ID, name="Équipe de démonstration")])

    @app.post("/rest/tempo-teams/2/team/members")
    def members():
        payload = request.get_json()
        return jsonify(
            [dict(member=user) for user in USERS.values()]
            if str(TEAM_ID) in [str(value) for value in payload.get("ids", [])]
            else []
        )

    @app.post("/rest/tempo-timesheets/4/worklogs/search")
    def tempo_worklogs():
        payload = request.get_json()
        try:
            start = date.fromisoformat(payload["from"])
            end = date.fromisoformat(payload["to"])
        except (KeyError, ValueError):
            abort(400)
        workers = payload.get("worker", list(USERS))
        if payload.get("teamId") and TEAM_ID not in payload["teamId"]:
            return jsonify([])
        results = []
        for key, logs in WORKLOGS.items():
            for log in logs:
                if (
                    log["author"]["key"] in workers
                    and start <= date.fromisoformat(log["started"][:10]) <= end
                ):
                    results.append(
                        dict(
                            issue=dict(id=ISSUES[key]["id"], key=key),
                            worker=log["author"],
                            timeSpentSeconds=log["timeSpentSeconds"],
                            startDate=log["started"][:10],
                            comment=log["comment"],
                        )
                    )
        return jsonify(results)

    @app.get("/browse/<key>")
    def browse(key):
        key = resolve(key)
        return Response(
            f"<h1>{escape(key)} — {escape(ISSUES[key]['fields']['summary'])}</h1>"
            "<p>Fiche fictive de la démo ReSprint.</p>",
            mimetype="text/html",
        )

    return app


if __name__ == "__main__":
    run_fixture(create_mock_jira())
