# Sprint Review

Outil Python pour preparer une sprint review Jira en listant les tickets du sprint
qui ne sont pas termines alors que du temps Tempo a ete consomme pendant la
periode du sprint.

## Installation

```bash
uv sync
cp .env.example .env
```

Renseigner ensuite `.env` avec l'authentification Jira.
Par defaut, le temps consomme est lu depuis les worklogs Jira, donc le token
Tempo n'est pas requis.

Pour Jira Cloud en basic auth, Atlassian attend generalement l'email du compte
comme username avec un API token. Pour Jira Server/Data Center, un username de
type `prenom.nom` peut etre valide selon la configuration. Si tu utilises un PAT
Bearer, configure `JIRA_AUTH_METHOD=bearer`; dans ce cas `JIRA_USERNAME` n'est
pas necessaire.

Pour Jira Data Center, garde `JIRA_REST_API_VERSION=2`. Les endpoints de search,
comments et worklogs utiliseront alors `/rest/api/2`.
Le chemin nominal utilise toujours l'API Agile Data Center pour recuperer le
sprint et les issues du sprint (`/rest/agile/1.0/...`), puis enrichit les details
des issues via l'API REST v2.

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

Si necessaire, tu peux fournir directement les dates du sprint et passer par JQL:

```bash
uv run sprint-review \
  --sprint-id 456 \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --jql 'project = ABC'
```

Pour forcer la source des temps:

```bash
uv run sprint-review --sprint-id 456 --board-id 123 --worklog-source jira
uv run sprint-review --sprint-id 456 --board-id 123 --worklog-source tempo
```

Le rapport organise les issues en trois sections:

- tickets termines avec un temps consomme superieur a l'estimation originale;
- tickets non termines avec au moins `--min-hours` consommees dans Tempo;
- tickets non commences, c'est-a-dire encore en categorie Jira `new` sans temps
  Tempo significatif.

Pour ces issues, le rapport ajoute aussi les commentaires Jira crees pendant la
periode du sprint, quand il y en a.

Le tableau du rapport contient: issue key, epopee, priorite, fixVersion, temps
original estime, temps restant estime, temps total consomme, temps consomme
durant le sprint, booleen de depassement de l'estimation originale, temps
consomme par utilisateur et commentaires durant le sprint.

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

## Integration continue

GitHub Actions execute les memes controles sur les push et pull requests vers
`main`:

```bash
uv run ruff format --check
uv run ruff check
uv run pytest
```

## Sources API

- Jira Software Agile API: sprint et issues de sprint.
  https://developer.atlassian.com/cloud/jira/software/rest/api-group-sprint/
- Jira Cloud issue search/JQL.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
- Jira Cloud issue worklogs.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-worklogs/
- Tempo Cloud API v4: worklogs filtres par `from`, `to` et `issueId`.
  https://apidocs.tempo.io/
