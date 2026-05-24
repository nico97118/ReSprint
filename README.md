# ReSprint

Outil Python pour preparer une review Jira sur un sprint ou une periode
personnalisee. ReSprint identifie les tickets qui meritent discussion, notamment
ceux qui ne sont pas termines alors que du temps a ete consomme pendant la
periode analysee.

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

Si le parent Jira est stocke dans un champ custom, configure
`RESPRINT_PARENT_FIELD`. L'ancien nom `RESPRINT_EPIC_FIELD` reste lu comme alias
de compatibilite.

## Utilisation

Avec un board Jira Software:

```bash
uv run resprint --board-id 123 --sprint-id 456 --format markdown
```

Sans board, via JQL:

```bash
uv run resprint --sprint-id 456 --jql 'project = ABC' --format json
```

Sans sprint Jira, via une periode et une requete JQL:

```bash
uv run resprint \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --sprint-name "Iteration mai" \
  --jql 'project = ABC AND fixVersion = 2026.05' \
  --tempo-team-id 42 \
  --format html \
  --output review.html
```

Dans ce mode, la requete JQL definit les fiches considerees comme dans la
periode. Si `--tempo-team-id` est fourni, la section hors sprint liste les fiches
bookees par l'equipe Tempo pendant la periode mais absentes du resultat JQL.

Options utiles:

```bash
uv run resprint --sprint-id 456 --board-id 123 --min-hours 2 --output review.md
uv run resprint --sprint-id 456 --board-id 123 --format html --output review.html
```

Interface web locale:

```bash
uv run resprint --serve
```

Le serveur ecoute par defaut sur `http://127.0.0.1:5000`. Cette interface
utilise `JIRA_PROJECT_KEY` pour lister les boards du projet, puis les sprints
actifs et clos du board selectionne. Le rapport est genere en synchrone au clic
sur `Generer`; le mode export CLI reste disponible.

La page d'accueil propose deux modes:

- `Analyse par sprint Jira`, ouvert par defaut, pour selectionner un board, une
  equipe Tempo optionnelle, puis un sprint;
- `Analyse par periode et JQL`, replie par defaut, pour renseigner une date de
  debut, une date de fin, une requete JQL et une equipe Tempo optionnelle.

Dans le mode periode/JQL, la requete JQL est affichee dans le header du rapport.
Si une equipe Tempo est selectionnee, la section hors sprint represente les
fiches bookees par cette equipe pendant la periode mais absentes du resultat JQL.

Depuis la page de rapport HTML, le bouton `Exporter` permet de telecharger le
rapport courant en JSON ou en Markdown sans relancer l'analyse. Ces exports
incluent aussi la section hors sprint quand elle existe.

Si necessaire, tu peux fournir directement les dates du sprint et passer par JQL:

```bash
uv run resprint \
  --sprint-id 456 \
  --sprint-start 2026-05-01 \
  --sprint-end 2026-05-15 \
  --jql 'project = ABC'
```

Pour forcer la source des temps:

```bash
uv run resprint --sprint-id 456 --board-id 123 --worklog-source jira
uv run resprint --sprint-id 456 --board-id 123 --worklog-source tempo
```

Le rapport organise les issues en trois sections:

- tickets termines avec un temps consomme superieur a l'estimation originale;
- tickets non termines avec au moins `--min-hours` consommees dans Tempo;
- tickets non commences, c'est-a-dire encore en categorie Jira `new` sans temps
  Tempo significatif.

Pour ces issues, le rapport ajoute aussi les commentaires Jira crees pendant la
periode du sprint, quand il y en a.

Le tableau du rapport contient: issue key, titre, type d'issue, parent,
temps original estime, temps restant estime, temps total consomme et temps
consomme durant le sprint. Les details de ligne ajoutent la priorite, la
fixVersion, le temps consomme par utilisateur et les commentaires durant le
sprint.

## Tests

```bash
uv run pytest
```

## Architecture

Le code applicatif est organise par responsabilite:

- `resprint.models` et `resprint.analysis`: modeles metier et analyse de sprint;
- `resprint.helpers`: helpers d'acces Jira et Tempo;
- `resprint.report`: construction des donnees du rapport;
- `resprint.exporters`: exports markdown et JSON;
- `resprint.frontend`: interface Flask locale, templates, assets et rendu HTML;
- `resprint.cli`: point d'entree en ligne de commande.

Les modules metier ne dependent pas de Flask ni du rendu HTML. Les helpers Jira
et Tempo isolent les appels reseau. Le frontend consomme les objets metier deja
analyses.

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

## Licence

ReSprint est distribue sous licence Apache-2.0. Voir [LICENSE](LICENSE)
et [NOTICE](NOTICE).

## Sources API

- Jira Software Agile API: sprint et issues de sprint.
  https://developer.atlassian.com/cloud/jira/software/rest/api-group-sprint/
- Jira Cloud issue search/JQL.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/
- Jira Cloud issue worklogs.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-worklogs/
- Tempo Cloud API v4: worklogs filtres par `from`, `to` et `issueId`.
  https://apidocs.tempo.io/
