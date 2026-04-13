from __future__ import annotations
from pathlib import Path
from typing import Any
class LogisticsSQLTemplateRegistry:
    """SQL 模板注册表（V7）。"""
    def __init__(self, base_dir: str | None = None) -> None:
        default_base_dir = Path(__file__).resolve().parent.parent / 'config' / 'sql_templates'
        self.base_dir = Path(base_dir) if base_dir else default_base_dir
    def get_template_path(self, sql_template_id: str | None) -> Path | None:
        if not sql_template_id:
            return None
        relative = Path(*sql_template_id.split('.')).with_suffix('.sql')
        path = self.base_dir / relative
        return path if path.exists() else None
    def load_sql(self, sql_template_id: str | None) -> str | None:
        path = self.get_template_path(sql_template_id)
        if not path:
            return None
        return path.read_text(encoding='utf-8')
    def describe(self, sql_template_id: str | None) -> dict[str, Any]:
        path = self.get_template_path(sql_template_id)
        return {'sql_template_id': sql_template_id, 'exists': bool(path), 'path': str(path) if path else None}
