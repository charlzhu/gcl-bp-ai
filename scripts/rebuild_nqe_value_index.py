from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.app.models  # noqa: E402,F401  # 触发 NQE 模型注册
from backend.app.db.base import Base  # noqa: E402
from backend.app.services.nqe_metadata_sync import DEFAULT_CATALOG_ROOT, NqeMetadataSyncBuilder  # noqa: E402
from backend.app.services.nqe_value_index import NqeValueIndexBuilder  # noqa: E402


def parse_args() -> argparse.Namespace:
    """解析 CLI 参数。

    返回：
        argparse.Namespace，包含 catalog 根目录、版本、输出文件和本地 SQLite apply 参数。
    """

    parser = argparse.ArgumentParser(description="重建 NQE value index dry-run 摘要，默认不连接业务库。")
    parser.add_argument("--catalog-root", default=str(DEFAULT_CATALOG_ROOT), help="受控 catalog 根目录。")
    parser.add_argument("--metadata-version", default="nqe_value_index_v1", help="value index 元数据版本号。")
    parser.add_argument("--output-json", default=None, help="摘要输出 JSON 文件路径。")
    parser.add_argument("--limit-per-column", type=int, default=100, help="单字段最多候选值数量。")
    parser.add_argument("--top-k", type=int, default=10, help="保留给召回验收的 topK 参数，不触发业务库查询。")
    parser.add_argument("--apply-sqlite", default=None, help="可选：仅写入本地 SQLite 文件；默认不写任何数据库。")
    return parser.parse_args()


def write_json(path: Path, data: dict[str, object]) -> None:
    """写入 JSON 文件。

    参数：
        path: 输出路径。
        data: JSON 兼容摘要。
    返回：
        无返回值。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_sqlite(sqlite_path: Path, candidates, *, metadata_version: str) -> dict[str, int]:
    """将 value candidates 写入本地 SQLite 测试库。

    参数：
        sqlite_path: 本地 SQLite 文件路径，不读取正式数据库配置。
        candidates: catalog 样例值生成的候选。
        metadata_version: 写入版本号。
    返回：
        upsert 统计信息。
    """

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{sqlite_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        return NqeValueIndexBuilder().upsert_value_candidates(session, candidates, metadata_version=metadata_version)


def main() -> int:
    """CLI 入口。

    返回：
        进程退出码；0 表示 dry-run 或本地 SQLite apply 成功。
    """

    args = parse_args()
    metadata_bundle = NqeMetadataSyncBuilder(args.catalog_root, metadata_version=args.metadata_version).build()
    builder = NqeValueIndexBuilder()
    candidates, summary = builder.build_from_catalog_examples(metadata_bundle, max_values_per_column=args.limit_per_column)
    payload = summary.to_dict()
    payload["metadata_version"] = args.metadata_version
    payload["top_k"] = max(1, int(args.top_k))
    payload["dry_run"] = args.apply_sqlite is None
    payload["apply_status"] = "dry_run"

    if args.apply_sqlite:
        payload["sqlite_upsert"] = apply_sqlite(Path(args.apply_sqlite), candidates, metadata_version=args.metadata_version)
        payload["apply_status"] = "sqlite_applied"

    if args.output_json:
        write_json(Path(args.output_json), payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
