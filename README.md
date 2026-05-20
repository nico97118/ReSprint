# Sprint Review

Outil Python pour preparer une sprint review Jira en listant les tickets du sprint
qui ne sont pas termines alors que du temps Tempo a ete consomme pendant la
periode du sprint.

## Installation

```bash
uv sync
cp .env.example .env
```

Renseigner ensuite `.env` avec les tokens Jira et Tempo.

## Utilisation

Avec un board Jira Software:

```bash
uv run sprint-review --board-id 123 --sprint-id 456 --format markdown
```

Sans board, via JQL:

```bash
uv run sprint-review --sprint-id 456 --jql 'project = ABC' --format json
```

Options utiles:

```bash
uv run sprint-review --sprint-id 456 --board-id 123 --min-hours 2 --output review.md
```

Le rapport organise les issues en trois sections:

- tickets termines avec un temps consomme superieur a l'estimation originale;
- tickets non termines avec au moins `--min-hours` consommees dans Tempo;
- tickets non commences, c'est-a-dire encore en categorie Jira `new` sans temps
  Tempo significatif.

Pour ces issues, le rapport ajoute aussi les commentaires Jira crees pendant la
periode du sprint, quand il y en a.

Le tableau du rapport contient: issue key, epopee, priorite, fixVersion, temps
original estime, temps restant estime, temps consomme durant le sprint et
commentaires durant le sprint.

## Tests

```bash
uv run pytest
```

## Qualite code

```bash
uv run ruff format
uv run ruff check
```

## Hooks Git

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Les hooks verifient le formatage Ruff, le lint Ruff, les tests pytest et
empechent de committer un fichier `.env`.

## Sources API

- Jira Software Agile API: sprint et issues de sprint.
  https://developer.atlassian.com/cloud/jira/software/rest/api-group-sprint/
- Jira Cloud issue search/JQL.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
- Tempo Cloud API v4: worklogs filtres par `from`, `to` et `issueId`.
  https://apidocs.tempo.io/
