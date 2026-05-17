#!/usr/bin/env bash
set +e
cd /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai
STATUS=0

run() {
  echo
  echo "===== $* ====="
  "$@"
  local ec=$?
  echo "EXIT_CODE=$ec"
  if [ "$ec" -ne 0 ]; then
    STATUS=1
  fi
  return 0
}

run backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py::test_23_to_25_hefei_shenzhen_13_avg_fee_hyphen_range_answers_without_clarification -q
run backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py -q
run backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py -k "route_pricing or hefei_to_guangzhou" -q
run backend/.venv/bin/python -m pytest tests/business_acceptance/test_logistics*.py -q
run backend/.venv/bin/python -m compileall -q backend/app tests

run backend/.venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from backend.app.main import app

question = '23年-25年，3年间合肥-深圳13米均价分别是多少'
client = TestClient(app)
resp = client.post('/api/v1/logistics/data-qa/query', json={
    'question': question,
    'use_llm': False,
})
print('status=', resp.status_code)
body = resp.json()
data = body.get('data') or {}
print('needs_clarification=', data.get('needs_clarification'))
print('answer_summary=', data.get('answer_summary'))
rows = (data.get('result_table') or {}).get('rows') or []
print('rows=', rows)
assert resp.status_code == 200
assert data.get('needs_clarification') is False
rows_by_year = {int(row['biz_year']): row for row in rows}
assert set(rows_by_year) == {2023, 2024, 2025}
assert rows_by_year[2023]['avg_fee'] is None
assert rows_by_year[2024]['avg_fee'] is None
assert int(rows_by_year[2025]['avg_fee'] or 0) == 9623
assert int(rows_by_year[2025]['total_fee'] or 0) == 28870
assert int(rows_by_year[2025]['shipment_trip_count'] or 0) == 3
assert int(rows_by_year[2025]['row_count'] or 0) == 3
for token in ('合肥', '深圳', '2023年', '2024年', '2025年'):
    assert token in (data.get('answer_summary') or '')
PY

run python - <<'PY'
from pathlib import Path
import re
import subprocess

repo = Path('/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai')
tracked = ['backend/app/domains/logistics/services/slot_extractor.py']
untracked = ['tests/business_acceptance/test_logistics_route_pricing_hefei_maanshan.py']
diff = subprocess.run(['git', 'diff', '--', *tracked], cwd=repo, text=True, capture_output=True, check=True).stdout
for rel in untracked:
    path = repo / rel
    if path.exists():
        diff += '\n' + subprocess.run(
            ['git', 'diff', '--no-index', '--', '/dev/null', rel],
            cwd=repo,
            text=True,
            capture_output=True,
        ).stdout
patterns = {
    'hardcoded_secret': re.compile(r"^\+.*(?i:(api_key|secret|password|token|passwd))\s*=\s*['\"][^'\"]{6,}['\"]"),
    'shell_injection': re.compile(r"^\+.*(os\.system\(|subprocess.*shell=True)"),
    'dangerous_eval_exec': re.compile(r"^\+.*(\beval\(|\bexec\()"),
    'pickle_load': re.compile(r"^\+.*pickle\.loads?\("),
    'sql_injection_format': re.compile(r"^\+.*(execute\(f\"|\.format\(.*SELECT|\.format\(.*INSERT)"),
}
findings = []
for line in diff.splitlines():
    for name, pattern in patterns.items():
        if pattern.search(line):
            findings.append(f'{name}: {line}')
print('SCANNED_DIFF_LINES=', len(diff.splitlines()))
print('STATIC_SCAN_FINDINGS=', len(findings))
for item in findings:
    print(item)
assert not findings
PY

(
  cd frontend
  run npm run build
)

run backend/.venv/bin/python -m pytest tests/business_acceptance -q
run backend/.venv/bin/python -m pytest tests -q

exit $STATUS
