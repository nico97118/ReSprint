"""Read-only Conduit fixture including reviewer decisions and name resolution."""

from copy import deepcopy

from flask import Flask, Response, jsonify, request
from markupsafe import escape

from resprint.demo.data import REVISIONS, TOKEN, USERS, phid
from resprint.demo.server import run_fixture


def _indexed(prefix: str) -> list[str]:
    values = []
    index = 0
    while f"{prefix}[{index}]" in request.form:
        values.append(request.form[f"{prefix}[{index}]"])
        index += 1
    return values


def _paged(items: list[dict], size: int = 2) -> dict:
    after = int(request.form.get("after", "0"))
    remaining = [item for item in items if int(item["id"]) > after]
    page = remaining[:size]
    cursor = str(page[-1]["id"]) if len(remaining) > size else None
    return dict(data=page, cursor=dict(limit=size, after=cursor, before=None))


def create_mock_phorge() -> Flask:
    """Create the read-only Phorge endpoints consumed by ReSprint."""
    app = Flask(__name__)

    @app.post("/api/<method>")
    def conduit(method: str):
        if request.form.get("api.token") != TOKEN or request.headers.get(
            "Authorization"
        ) not in (None, f"oauth {TOKEN}"):
            return jsonify(
                result=None,
                error_code="ERR-INVALID-AUTH",
                error_info="Invalid demo token",
            ), 401
        if method == "differential.query":
            ids = _indexed("ids")
            result = [
                deepcopy(REVISIONS[int(rid)])
                for rid in ids
                if rid.isdigit() and int(rid) in REVISIONS
            ]
            for revision in result:
                revision.pop("reviewers")
        elif method == "differential.revision.search":
            ids = set(_indexed("constraints[ids]"))
            data = []
            for rid, revision in REVISIONS.items():
                if str(rid) not in ids:
                    continue
                item = dict(
                    id=rid, phid=phid("DREV", str(rid)), fields=deepcopy(revision)
                )
                item["fields"].pop("reviewers")
                item["attachments"] = (
                    {"reviewers": {"reviewers": deepcopy(revision["reviewers"])}}
                    if request.form.get("attachments[reviewers]") in ("1", "true")
                    else {}
                )
                data.append(item)
            result = _paged(sorted(data, key=lambda item: item["id"]))
        elif method == "diffusion.repository.search":
            requested = set(_indexed("constraints[phids]"))
            data = [
                dict(id=index, phid=phid("REPO", name), fields={"name": name})
                for index, name in enumerate(("core", "web"), 1)
                if phid("REPO", name) in requested
            ]
            result = _paged(data, 1)
        elif method == "phid.query":
            names = {
                phid("USER", key): user["displayName"] for key, user in USERS.items()
            }
            names[phid("PROJ", "team")] = "Équipe architecture"
            result = {
                key: dict(phid=key, name=names[key], fullName=names[key])
                for key in _indexed("phids")
                if key in names
            }
        else:
            return jsonify(
                result=None,
                error_code="ERR-UNKNOWN-METHOD",
                error_info="Unknown demo method",
            ), 404
        return jsonify(result=result, error_code=None, error_info=None)

    @app.get("/D<int:review_id>")
    def review(review_id: int):
        revision = REVISIONS.get(review_id)
        if revision is None:
            return "Review absente du jeu de démonstration.", 404
        return Response(
            f"<h1>D{review_id} — {escape(revision['title'])}</h1>"
            f"<p>{escape(revision['statusName'])}</p>"
            "<p>Review fictive de la démo ReSprint.</p>",
            mimetype="text/html",
        )

    @app.get("/healthz")
    def health():
        return "ok"

    return app


if __name__ == "__main__":
    run_fixture(create_mock_phorge())
