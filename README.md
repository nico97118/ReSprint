# ReSprint

Outil Python pour preparer une review Jira sur un sprint ou une periode
personnalisee. ReSprint identifie les tickets qui meritent discussion, notamment
ceux qui ne sont pas termines alors que du temps a ete consomme pendant la
periode analysee.

## Installation

```bash
uv sync
source .venv/bin/activate
cp .env.example .env
cp setting.toml.example setting.toml
```

Renseigner ensuite `.env` avec les secrets:
- `JIRA_API_TOKEN`, obligatoire pour fonctionner;
- `TEMPO_API_TOKEN`, uniquement si `worklog_source = "tempo"`.

Le fichier `.env` est chargé avec `python-dotenv`. La syntaxe standard est donc
supportée, notamment `export KEY=value`, les valeurs entre guillemets, les commentaires
en fin de ligne et l'expansion de variables déjà présentes dans l'environnement.
Les variables déjà définies dans l'environnement ne sont pas remplacées par
`.env`.

La configuration non-secrete se trouve dans `setting.toml` a la racine du projet.
Le fichier `setting.toml.example` fournit un point de depart. Les cles lues par le code sont les suivantes:

```toml
[jira]
base_url = "https://your-domain.atlassian.net"
project_key = "ABC"
rest_api_version = "2"

[resprint]
worklog_source = "jira"
done_status_categories = ["done"]
min_seconds = 1
log_level = "error"
ignored_changelog_fields = ["worklogid", "timeestimate", "timespent"]
parent_field = "customfield_10014"
```

- `jira.base_url` est obligatoire.
- `jira.project_key` est optionnel pour la ligne de commande, mais requis pour
  lister les boards dans l'interface web locale.
- `jira.rest_api_version` est optionnel; la valeur par defaut est `2` et la
  valeur doit etre `2` ou `3`.
- `resprint.worklog_source` est optionnel; la valeur par defaut est `jira` et
  la valeur doit etre `jira` ou `tempo`.
- `resprint.done_status_categories` est optionnel; la valeur par defaut est
  `["done"]`.
- `resprint.min_seconds` est optionnel; la valeur par defaut est `1`.
- `resprint.log_level` est optionnel; la valeur par defaut est `error` et les
  valeurs supportees sont `debug`, `info`, `warning`, `error` et `critical`.
- `resprint.ignored_changelog_fields` est optionnel; la valeur par defaut est
  `["worklogid", "timeestimate", "timespent"]`.
- `resprint.parent_field` est optionnel; il permet de lire un champ Jira
  custom qui stocke la relation parent/epic.

Pour Jira Data Center, garde `rest_api_version=2`. Les endpoints de search,
comments et worklogs utiliseront alors `/rest/api/2`.
Le chemin nominal utilise toujours l'API Agile Data Center pour recuperer le
sprint et les issues du sprint (`/rest/agile/1.0/...`), puis enrichit les details
des issues via l'API REST v2 ou v3 selon la configuration.

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
utilise `jira.project_key` pour lister les boards du projet, puis les sprints
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

Les graphiques KPI du rapport HTML utilisent Chart.js et les icones utilisent
Material Design Icons. Ces assets sont embarques localement dans l'application
et servis par ReSprint via `/assets/...`; la consultation du rapport ne depend
donc pas d'un CDN ou d'un acces internet.

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

- tickets termines, avec une coloration quand le temps total consomme depasse
  l'estimation originale;
- tickets non termines avec au moins `--min-hours` consommees dans Tempo;
- tickets non commences, c'est-a-dire encore en categorie Jira `new` sans temps
  Tempo significatif.

Pour ces issues, le rapport ajoute aussi les commentaires Jira et l'activite Jira
du ticket crees pendant la periode du sprint, quand il y en a. L'activite est
extraite du changelog Jira via `expand=changelog`, puis filtree localement sur
la periode analysee.

Le tableau du rapport contient: issue key, titre, type d'issue, statut, parent,
temps original estime, temps restant estime, temps total consomme et temps
consomme durant le sprint. Chaque ligne peut etre deployee pour consulter les
details: progression des temps, priorite, fixVersion, temps consomme par
utilisateur, commentaires durant le sprint et changements Jira synthetises sous
la forme qui/quand/quoi. Les sections commentaires et activite affichent un
badge avec le nombre d'elements disponibles; les commentaires sont ouverts par
defaut, l'activite est repliee par defaut.

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

Les assets tiers du frontend sont geres avec un npm minimal. Les fichiers
vendored sont commites dans `src/resprint/frontend/static/vendor/`, donc npm
n'est pas requis pour lancer ReSprint. Les CSS et JS applicatifs sont minifies
dans `src/resprint/frontend/static/min/` et servis depuis `/assets/min/...`.
Pour regenerer les assets depuis le lockfile:

```bash
npm ci
npm run vendor
npm run minify
```

Pour verifier que les fichiers minifies sont a jour sans les regenerer:

```bash
npm run minify:check
```

Pour tout rafraichir en une fois:

```bash
npm run assets
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
la coherence des assets minifies quand le frontend est modifie, tout en
empechant de committer un fichier `.env`.

## Integration continue

GitHub Actions execute les memes controles sur les push et pull requests vers
`dev`:

```bash
npm run minify:check
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
- Jira Cloud issue API: details d'issue et changelog via `expand=changelog`.
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
- Tempo Cloud API v4: worklogs filtres par `from`, `to` et `issueId`.
  https://apidocs.tempo.io/
- Chart.js: graphiques KPI du rapport HTML.
  https://www.chartjs.org/
- Material Design Icons: icones de l'interface HTML.
  https://pictogrammers.com/library/mdi/
