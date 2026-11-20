#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
image=${1:-resprint:local}
scratch=$(mktemp -d)
container=

cleanup() {
  local status=$?
  if (( status != 0 )) && [[ -n "$container" ]]; then
    docker logs "$container" >&2 || true
  fi
  if [[ -n "$container" ]]; then docker rm -f "$container" >/dev/null || true; fi
  rm -rf "$scratch"
}
trap cleanup EXIT

chmod 755 "$scratch"
cat > "$scratch/setting.toml" <<'TOML'
[jira]
base_url = "http://127.0.0.1:9"
project_key = "ABC"
[resprint]
hours_per_day = 7.5
TOML
chmod 644 "$scratch/setting.toml"

# Test the installed CLI and non-root runtime without touching external services.
docker run --rm "$image" resprint --help > "$scratch/help.txt"
grep -Fq -- '--sprint-id' "$scratch/help.txt"
test "$(docker run --rm "$image" python -c 'import os; print(os.getuid())')" = 10001

container=$(docker run -d --publish 127.0.0.1::5000 \
  --env JIRA_API_TOKEN=docker-smoke \
  --mount "type=bind,source=$scratch/setting.toml,target=/app/setting.toml,readonly" \
  "$image")
url="http://$(docker port "$container" 5000/tcp)"
python3 - "$url" <<'PY'
import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1]
deadline = time.monotonic() + 30
while True:
    try:
        with urllib.request.urlopen(url + '/healthz', timeout=3) as response:
            assert response.read() == b'ok'
        break
    except (OSError, urllib.error.URLError):
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.2)

# Assets must come from the installed package, not a mounted source checkout.
for asset in ('min/common.min.css', 'min/table.min.js', 'vendor/chartjs/chart.umd.js'):
    with urllib.request.urlopen(url + '/assets/' + asset, timeout=3) as response:
        assert response.read(), asset

# Invalid report input renders the packaged error template without calling Jira.
try:
    urllib.request.urlopen(url + '/report', timeout=3)
except urllib.error.HTTPError as error:
    assert error.code == 400
    assert b'<!doctype html>' in error.read()
else:
    raise AssertionError('Expected invalid report parameters to return HTTP 400')
PY

# Run the exact healthcheck command from the image definition.
docker exec "$container" python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).close()"
echo "Docker smoke test passed: non-root runtime, CLI, web health, assets and templates."
