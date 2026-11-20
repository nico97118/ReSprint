"""Fictional, deterministic Jira/Tempo/Phorge data shared by demo services."""

from datetime import UTC, datetime

TOKEN = "resprint-demo"
SPRINT_ID = 456
TEAM_ID = 42
REVIEW_FIELD = "customfield_reviews"
START_DATE = "2026-11-02"
END_DATE = "2026-11-13"
USERS = {
    key: dict(name=key, key=key, displayName=name, active=True)
    for key, name in (
        ("alice", "Alice Martin"),
        ("bob", "Bob Leroy"),
        ("carol", "Carol Nguyen"),
    )
}
SPRINT = dict(
    id=SPRINT_ID,
    name="Sprint de démonstration",
    state="closed",
    startDate=START_DATE + "T09:00:00.000+0000",
    endDate=END_DATE + "T18:00:00.000+0000",
)
# number, title, Jira category, review references, period hours, issue type
ISSUE_SPECS = (
    (1, "Paiement livré", "done", (101,), 7, "Story"),
    (2, "Export prêt à clôturer", "indeterminate", (102,), 7, "Story"),
    (
        3,
        "API en attente de validation obligatoire",
        "indeterminate",
        (103,),
        3.5,
        "Task",
    ),
    (4, "Fiche terminée avec review ouverte", "done", (104,), 2, "Bug"),
    (5, "Travail non commencé", "new", (), 0, "Task"),
    (6, "Prototype abandonné", "indeterminate", (105,), 1, "Task"),
    (
        7,
        "Reviews terminées, fiche encore ouverte",
        "indeterminate",
        (106, 105),
        2,
        "Story",
    ),
    (8, "Sans temps, mais review à clôturer", "indeterminate", (108,), 0, "Task"),
    (9, "Review inaccessible", "indeterminate", (109,), 1, "Bug"),
    (10, "Review partagée avec le paiement", "done", (101,), 3, "Sub-task"),
    (11, "Support hors sprint", "indeterminate", (110,), 3.5, "Task"),
    (12, "Migration historique paginée", "done", (), 30, "Task"),
)
ISSUES = {}
WORKLOGS = {}
COMMENTS = {}
for number, title, category, refs, hours, kind in ISSUE_SPECS:
    key = f"ABC-{number}"
    issue_id = str(10000 + number)
    ISSUES[key] = dict(
        id=issue_id,
        key=key,
        fields=dict(
            summary=title,
            project={"key": "ABC"},
            status={
                "name": {
                    "done": "Terminé",
                    "new": "À faire",
                    "indeterminate": "En cours",
                }[category],
                "statusCategory": {"key": category},
            },
            assignee=USERS["alice"],
            issuetype={"name": kind},
            priority={"name": "High" if number == 4 else "Medium"},
            fixVersions=[{"name": "1.2"}],
            parent={"key": "ABC-100"},
            timeoriginalestimate=7 * 3600,
            timeestimate=0 if category == "done" else 3600,
            **{REVIEW_FIELD: [f"D{ref}" for ref in refs]},
        ),
    )
    seconds = int(hours * 3600)
    count = 120 if number == 12 else int(bool(seconds))
    logs = [
        dict(
            id=f"{number}-{i}",
            issueId=issue_id,
            author=USERS["alice" if i % 2 == 0 else "bob"],
            timeSpentSeconds=seconds // count,
            started="2026-11-05T09:00:00.000+0000",
            comment="Travail de démonstration",
        )
        for i in range(count)
    ]
    # Earlier time contributes to global totals, not to sprint-period time.
    if hours:
        logs.append(
            dict(
                id=f"{number}-before",
                issueId=issue_id,
                author=USERS["carol"],
                timeSpentSeconds=3600,
                started="2026-10-20T09:00:00.000+0000",
                comment="Préparation avant le sprint",
            )
        )
    WORKLOGS[key] = logs
    COMMENTS[key] = [
        dict(
            id=f"{number}-{i}",
            issueId=issue_id,
            author=USERS["bob"],
            created="2026-11-06T10:00:00.000+0000",
            body=f"Commentaire {i + 1} : *validation* et [documentation|https://example.test].",
        )
        for i in range(3)
    ]
ISSUES["ABC-100"] = dict(
    id="10100",
    key="ABC-100",
    fields=dict(
        summary="Épopée de démonstration",
        project={"key": "ABC"},
        issuetype={"name": "Epic"},
        status={"name": "En cours", "statusCategory": {"key": "indeterminate"}},
    ),
)
SPRINT_KEYS = tuple(key for key in ISSUES if key not in {"ABC-11", "ABC-100"})


def phid(kind: str, key: str) -> str:
    """Return a deterministic fictional Phorge identifier."""
    return f"PHID-{kind}-{key}"


def decision(user: str, status: str = "accepted", blocking: bool = False) -> dict:
    """Build a reviewer attachment entry."""
    return dict(
        reviewerPHID=phid("PROJ" if user == "team" else "USER", user),
        status=status,
        isBlocking=blocking,
    )


REVISIONS = {}
for rid, code, title, reviewers in (
    (101, "3", "Paiement livré", [decision("alice"), decision("bob")]),
    (102, "2", "Export accepté", [decision("bob"), decision("carol")]),
    (
        103,
        "0",
        "API avec approbation obligatoire",
        [decision("alice"), decision("bob"), decision("team", "blocking", True)],
    ),
    (
        104,
        "1",
        "Correctif avec changements demandés",
        [decision("alice"), decision("bob", "rejected")],
    ),
    (105, "4", "Prototype abandonné", []),
    (106, "3", "Refonte intégrée", [decision("alice"), decision("carol")]),
    (
        108,
        "2",
        "Optimisation sans temps dans le sprint",
        [decision("alice"), decision("bob")],
    ),
    (110, "0", "Support hors périmètre", [decision("carol", "added")]),
):
    REVISIONS[rid] = dict(
        id=rid,
        title=title,
        status=code,
        statusName={
            "0": "Needs Review",
            "1": "Needs Revision",
            "2": "Accepted",
            "3": "Closed",
            "4": "Abandoned",
        }[code],
        authorPHID=phid("USER", "alice"),
        repositoryPHID=phid("REPO", "web" if rid % 2 else "core"),
        dateCreated=str(int(datetime(2026, 11, 3, tzinfo=UTC).timestamp())),
        reviewers=reviewers,
    )
