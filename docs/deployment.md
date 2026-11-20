# Docker deployment

[Back to README](../README.md)

Build the image from the repository root, then mount your existing
`settings.toml` read-only and provide API tokens at runtime:

```bash
docker build -t resprint:local .
docker run -d --name resprint \
  --publish 127.0.0.1:5000:5000 \
  --env-file .env \
  --mount "type=bind,source=$PWD/settings.toml,target=/app/settings.toml,readonly" \
  resprint:local
```

Open `http://127.0.0.1:5000/`. Use `docker logs resprint` for startup and
access logs, and `curl --fail http://127.0.0.1:5000/healthz` to check the web
process independently of Jira, Tempo or Phorge. Docker also runs this health
check automatically. To recreate the container after rebuilding or changing
configuration, remove it first with `docker rm -f resprint`.

The image installs the locked `server` extra and the application as a regular
package in a two-stage Python 3.13 build. The runtime includes Gunicorn, the CLI,
templates and bundled frontend assets; it runs as UID/GID 10001. Source secrets,
local configuration and development dependencies are excluded from the image.
No npm installation is needed to build or run it.

Docker environment files use plain `KEY=value` lines: omit shell quotes and
variable interpolation. Pass `JIRA_API_TOKEN` and, when enabled,
`PHORGE_API_TOKEN` this way or through your platform's secret mechanism. Mounted
configuration and certificate files must be readable by UID 10001. For a custom
CA, add a read-only mount and set `jira.ca_bundle` or `phorge.ca_bundle` to its
path **inside** the container. The web service needs outbound access to the
configured services and no persistent volume.

Gunicorn defaults to two synchronous workers and a 300-second worker timeout
because report generation makes multiple Jira/Tempo/Phorge requests. Tune worker
count and timeout for representative workloads; each report also uses the
configured request concurrency. Override the complete Gunicorn argument set
through `GUNICORN_CMD_ARGS`, for example:

```bash
docker run -d --name resprint \
  --publish 127.0.0.1:5000:5000 \
  --env-file .env \
  --env 'GUNICORN_CMD_ARGS=--bind=0.0.0.0:5000 --workers=2 --timeout=600 --no-control-socket --access-logfile=- --error-logfile=-' \
  --mount "type=bind,source=$PWD/settings.toml,target=/app/settings.toml,readonly" \
  resprint:local
```

Keep port 5000 inside the container for the built-in health check. For shared
hosting, place the service behind your authenticated HTTPS reverse proxy and
align its timeout with long report requests. Viewers use the configured Jira
account's permissions.

The same image can run CLI exports by overriding the server command:

```bash
docker run --rm --env-file .env \
  --mount "type=bind,source=$PWD/settings.toml,target=/app/settings.toml,readonly" \
  resprint:local resprint --sprint-id 456 --tempo-worker alice --format json \
  > report.json
```

To run the image checks locally, use `bash scripts/docker-smoke.sh resprint:local`.
CI builds the image and runs the same checks for the non-root runtime, assets,
full web report and JSON CLI export against local Jira/Tempo and Phorge
fixtures. No real service is contacted.
