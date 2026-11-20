#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
image=${1:-resprint:local}
scratch=$(mktemp -d)
network="resprint-${scratch##*/}"
container=
jira=
phorge=

cleanup() {
  local status=$?
  if (( status != 0 )); then
    for service in "$container" "$jira" "$phorge"; do
      if [[ -n "$service" ]]; then docker logs "$service" >&2 || true; fi
    done
  fi
  for service in "$container" "$jira" "$phorge"; do
    if [[ -n "$service" ]]; then docker rm -f "$service" >/dev/null || true; fi
  done
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -rf "$scratch"
}
trap cleanup EXIT

chmod 755 "$scratch"
cat > "$scratch/setting.toml" <<'TOML'
[jira]
base_url = "http://jira:8000"
project_key = "ABC"
[resprint]
hours_per_day = 7.5
out_of_sprint_analysis = true
[phorge]
enabled = true
jira_fields = ["customfield_reviews"]
base_url = "http://phorge:8000"
TOML
chmod 644 "$scratch/setting.toml"

docker run --rm "$image" resprint --help > "$scratch/help.txt"
grep -Fq -- '--demo' "$scratch/help.txt"
test "$(docker run --rm "$image" python -c 'import os; print(os.getuid())')" = 10001

docker network create "$network" >/dev/null
jira=$(docker run -d --network "$network" --network-alias jira --no-healthcheck \
  "$image" python -m resprint.demo.mock_jira --host 0.0.0.0)
phorge=$(docker run -d --network "$network" --network-alias phorge --no-healthcheck \
  "$image" python -m resprint.demo.mock_phorge --host 0.0.0.0)

# Wait for fixtures before asking the packaged application to generate a report.
docker run --rm -i --network "$network" "$image" python - <<'PY'
import time
import urllib.error
import urllib.request

for name in ('jira', 'phorge'):
    deadline = time.monotonic() + 20
    while True:
        try:
            with urllib.request.urlopen(f'http://{name}:8000/healthz', timeout=1) as response:
                assert response.read() == b'ok'
            break
        except (OSError, urllib.error.URLError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
PY

runtime_args=(
  --network "$network"
  --env JIRA_API_TOKEN=resprint-demo
  --env PHORGE_API_TOKEN=resprint-demo
  --mount "type=bind,source=$scratch/setting.toml,target=/app/setting.toml,readonly"
)
container=$(docker run -d "${runtime_args[@]}" --publish 127.0.0.1::5000 "$image")
url="http://$(docker port "$container" 5000/tcp)"
python3 - "$url" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

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

for asset in ('min/common.min.css', 'min/table.min.js', 'vendor/chartjs/chart.umd.js'):
    with urllib.request.urlopen(url + '/assets/' + asset, timeout=3) as response:
        assert response.read(), asset

with urllib.request.urlopen(url + '/', timeout=10) as response:
    assert 'Sprint de démonstration' in response.read().decode()
with urllib.request.urlopen(url + '/participants?sprint_id=456&tempo_team_id=42', timeout=10) as response:
    assert 'Alice Martin' in response.read().decode()
with urllib.request.urlopen(url + '/report?sprint_id=456&tempo_team_id=42', timeout=30) as response:
    report = response.read().decode()
assert 'À clôturer' in report
assert 'Équipe architecture' in report
assert 'issue-review-warning' in report

class ExportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_export = False
        self.data = ''
    def handle_starttag(self, tag, attrs):
        self.in_export = tag == 'script' and dict(attrs).get('id') == 'report-export-json'
    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_export = False
    def handle_data(self, data):
        if self.in_export:
            self.data += data

parser = ExportParser()
parser.feed(report)
data = json.loads(parser.data)
heavy = next(item for item in data['completed'] if item['key'] == 'ABC-12')
assert heavy['total_seconds'] == 111600
assert len(heavy['comments']) == 3
assert [item['key'] for item in data['out_of_sprint']] == ['ABC-11']
reviews = {item['id']: item for item in data['code_reviews']['items']}
assert reviews[102]['ready_to_close'] is True
assert reviews[103]['pending_required_approval_count'] == 1
assert reviews[108]['issue_keys'] == ['ABC-8']
assert reviews[109]['state'] == 'unknown'
assert 110 not in reviews
PY

docker exec "$container" python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).close()"
docker run --rm "${runtime_args[@]}" "$image" \
  resprint --sprint-id 456 --tempo-team-id 42 --format json > "$scratch/report.json"
python3 - "$scratch/report.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as stream:
    report = json.load(stream)
assert len(report['completed']) == 4
assert len(report['code_reviews']['items']) == 8
assert report['code_reviews']['counts']['unknown'] == 1
PY
echo "Docker smoke test passed: non-root runtime, assets, Jira/Tempo/Phorge web report and CLI export."
