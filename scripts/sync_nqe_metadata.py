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

from backend.app.db.base import Base  # noqa: E402
from backend.app.services.nqe_metadata_sync import (  # noqa: E402
    DEFAULT_CATALOG_ROOT,
    NqeMetadataSyncBuilder,
    upsert_nqe_metadata_bundle,
)


def parse_args() -> argparse.Namespace:
    """解析 CLI 参数。

    返回：
        argparse.Namespace，包含 catalog 根目录、输出文件、版本和本地 SQLite 写入路径。
    """

    parser = argparse.ArgumentParser(description="构建 NQE 元数据 dry-run 摘要，或写入本地 SQLite 测试库。")
    parser.add_argument(
        "--catalog-root",
        default=str(DEFAULT_CATALOG_ROOT),
        help="受控 catalog 根目录，默认读取物流 nl2sql_catalog。",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="dry-run 摘要输出 JSON 文件路径；不提供时仅打印摘要。",
    )
    parser.add_argument(
        "--metadata-version",
        default="nqe_catalog_v1",
        help="元数据版本号，默认 nqe_catalog_v1。",
    )
    parser.add_argument(
        "--domain",
        "--include-domain",
        dest="include_domains",
        action="append",
        default=None,
        help="可选：只同步指定业务域，可重复传入；默认不过滤保持全域 dry-run。",
    )
    parser.add_argument(
        "--apply-sqlite",
        default=None,
        help="可选：仅写入指定本地 SQLite 文件；默认不写任何数据库。",
    )
    return parser.parse_args()


def write_json(path: Path, data: dict[str, object]) -> None:
    """写入 JSON 文件。

    参数：
        path: 输出文件路径。
        data: 待写入的 JSON 兼容对象。
    返回：
        无返回值。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_sqlite(sqlite_path: Path, bundle) -> dict[str, int]:
    """将 bundle 写入本地 SQLite 文件。

    参数：
        sqlite_path: 本地 SQLite 文件路径；不会读取项目正式数据库配置。
        bundle: NqeMetadataSyncBuilder 生成的元数据包。
    返回：
        upsert 统计信息。
    """

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{sqlite_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        return upsert_nqe_metadata_bundle(session, bundle)


def main() -> int:
    """CLI 入口。

    返回：
        进程退出码；0 表示 dry-run 或本地 SQLite upsert 成功。
    """

    args = parse_args()
    # 中文注释：未传 --domain/--include-domain 时 include_domains=None，继续构建三域完整 bundle。
    builder = NqeMetadataSyncBuilder(args.catalog_root, metadata_version=args.metadata_version, include_domains=args.include_domains)
    bundle = builder.build()
    summary = bundle.to_summary()

    if args.apply_sqlite:
        summary["sqlite_upsert"] = apply_sqlite(Path(args.apply_sqlite), bundle)

    if args.output_json:
        write_json(Path(args.output_json), summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
