"""产销存 Excel 批量导入脚本。"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保能找到 backend 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.db.session import SessionLocal
from backend.app.domains.business_analysis.repositories.inventory_sales_production_repository import (
    InventorySalesProductionRepository,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.excel_parser import (
    InventorySalesProductionExcelParser,
)

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent

FILES = [
    ("2023年", WORKTREE_ROOT / "2023年产量与预算达成率分析.xlsx"),
    ("2024年", WORKTREE_ROOT / "经营数据汇总表2024年.xlsx"),
    ("2025年", WORKTREE_ROOT / "组件事业部月度产销存-2025年.xlsx"),
    ("2026年", WORKTREE_ROOT / "组件事业部月度产销存-2026.04.xlsx"),
]


def main() -> int:
    parser = InventorySalesProductionExcelParser()
    db = SessionLocal()
    repo = InventorySalesProductionRepository(db)
    total_facts = 0

    for label, path in FILES:
        if not path.exists():
            print(f"  SKIP {label}: 文件不存在 {path}")
            continue

        print(f"\n{'='*60}")
        print(f"  导入 {label}: {path.name}")
        print(f"{'='*60}")

        parsed = parser.parse_file(str(path))
        print(f"  解析完成：{parsed.monthly_fact_count} 行事实")

        workbook, created = repo.save_parsed_workbook(parsed)
        status = "新增" if created else "已存在（跳过）"
        print(f"  入库结果：workbook_id={workbook.id}，{status}")
        total_facts += parsed.monthly_fact_count if created else 0

    db.close()

    print(f"\n{'='*60}")
    print(f"  批量导入完成。总新增事实行数: {total_facts}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
