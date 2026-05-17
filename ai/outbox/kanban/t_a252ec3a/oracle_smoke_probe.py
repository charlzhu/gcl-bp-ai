from pathlib import Path
import os
import json
import socket
import importlib.util
import time

root = Path('/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai')
outdir = root / 'ai/outbox/kanban/t_a252ec3a'
outdir.mkdir(parents=True, exist_ok=True)
keys = [
    'SAP_ORACLE_HOST',
    'SAP_ORACLE_PORT',
    'SAP_ORACLE_SERVICE',
    'SAP_ORACLE_USER',
    'SAP_ORACLE_PASSWORD',
]

def read_env_values():
    vals = {}
    env_path = root / 'backend/.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in keys:
                vals[key] = value
    for key in keys:
        if os.environ.get(key):
            vals[key] = os.environ[key]
    return vals

vals = read_env_values()
result = {
    'executed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    'scope': 'read-only Oracle MID smoke test: dependency/config/connectivity only; no table export',
    'required_config_keys': keys,
    'config_presence': {key: bool(vals.get(key)) for key in keys},
    'dependency': {
        'oracledb': importlib.util.find_spec('oracledb') is not None,
        'cx_Oracle': importlib.util.find_spec('cx_Oracle') is not None,
    },
    'network_probe': None,
    'sql_probe': None,
    'status': 'blocked',
    'block_reason': None,
}
missing = [key for key in keys if not vals.get(key)]
if missing:
    result['block_reason'] = 'missing config keys: ' + ', '.join(missing)
elif not (result['dependency']['oracledb'] or result['dependency']['cx_Oracle']):
    result['block_reason'] = 'Oracle Python driver not installed (oracledb/cx_Oracle unavailable)'
else:
    host = vals['SAP_ORACLE_HOST']
    port = int(vals.get('SAP_ORACLE_PORT') or 1521)
    try:
        with socket.create_connection((host, port), timeout=5):
            result['network_probe'] = {'ok': True, 'timeout_seconds': 5}
    except Exception as exc:  # noqa: BLE001
        result['network_probe'] = {'ok': False, 'error_type': type(exc).__name__}
        result['block_reason'] = 'TCP connectivity failed before SQL probe'
    if result['network_probe'] and result['network_probe'].get('ok'):
        try:
            if result['dependency']['oracledb']:
                import oracledb
                dsn = oracledb.makedsn(host, port, service_name=vals['SAP_ORACLE_SERVICE'])
                conn = oracledb.connect(user=vals['SAP_ORACLE_USER'], password=vals['SAP_ORACLE_PASSWORD'], dsn=dsn)
            else:
                import cx_Oracle
                dsn = cx_Oracle.makedsn(host, port, service_name=vals['SAP_ORACLE_SERVICE'])
                conn = cx_Oracle.connect(user=vals['SAP_ORACLE_USER'], password=vals['SAP_ORACLE_PASSWORD'], dsn=dsn)
            cur = conn.cursor()
            cur.execute('SELECT 1 AS smoke_value FROM dual')
            row = cur.fetchone()
            cur.close()
            conn.close()
            result['sql_probe'] = {
                'ok': True,
                'query': 'SELECT 1 FROM dual',
                'row_count': 1,
                'value_ok': bool(row and row[0] == 1),
            }
            result['status'] = 'passed'
            result['block_reason'] = None
        except Exception as exc:  # noqa: BLE001
            result['sql_probe'] = {'ok': False, 'error_type': type(exc).__name__}
            result['block_reason'] = 'SQL probe failed; error details intentionally omitted to avoid leaking connection metadata'
(outdir / 'oracle_smoke_safe_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'status': result['status'],
    'config_presence': result['config_presence'],
    'dependency': result['dependency'],
    'network_probe': None if result['network_probe'] is None else result['network_probe'].get('ok'),
    'sql_probe': None if result['sql_probe'] is None else result['sql_probe'].get('ok'),
    'block_reason': result['block_reason'],
}, ensure_ascii=False))
