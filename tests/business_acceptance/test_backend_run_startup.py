from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_PY = ROOT / "backend" / "run.py"


def test_run_py_disables_uvicorn_reload_when_debugger_is_attached() -> None:
    """IDE 调试器附加时 run.py 不应再启用 uvicorn reload，避免重复派生进程和重复连接提示。"""
    source = RUN_PY.read_text(encoding="utf-8")

    assert "import sys" in source
    assert "sys.gettrace()" in source
    assert "debugger_attached" in source
    assert "reload_enabled" in source
    assert "reload=reload_enabled" in source
