#!/usr/bin/env python
"""NQE 元数据 retrieval chunk 向量索引 dry-run / apply 入口。

默认行为：
    只读取受控 catalog，复用 NQE-7 builder 生成 retrieval chunks，并输出待索引统计。
    默认不读取 .env、不连接 Milvus、不调用真实 embedding provider。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.nqe_metadata_sync import DEFAULT_CATALOG_ROOT  # noqa: E402
from backend.app.services.nqe_metadata_vector_index import NqeMetadataVectorIndexService  # noqa: E402


def parse_args() -> argparse.Namespace:
    """解析 CLI 参数。

    返回：
        argparse.Namespace，包含 catalog 根目录、版本、输出文件、批大小和是否真实写入。
    """

    parser = argparse.ArgumentParser(description="重建 NQE metadata retrieval chunks 向量索引，默认 dry-run。")
    parser.add_argument(
        "--catalog-root",
        default=str(DEFAULT_CATALOG_ROOT),
        help="受控 catalog 根目录，默认读取物流 nl2sql_catalog。",
    )
    parser.add_argument(
        "--metadata-version",
        default="nqe_catalog_v1",
        help="元数据版本号，默认 nqe_catalog_v1。",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="摘要 JSON 输出路径；不提供时仅打印到 stdout。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="apply 时 embedding 分批大小，dry-run 不使用。",
    )
    parser.add_argument(
        "--apply-milvus",
        action="store_true",
        help="显式开启真实向量写入；默认关闭。本脚本不读取 .env，缺真实依赖时 fail-closed。",
    )
    return parser.parse_args()


def write_json(path: Path, data: dict[str, object]) -> None:
    """写入 JSON 摘要。

    参数：
        path: 输出文件路径。
        data: JSON 兼容字典。
    返回：
        无返回值。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    """CLI 主入口。

    返回：
        0 表示 dry-run 成功或真实写入成功；非 0 表示 fail-closed。
    """

    args = parse_args()
    service = NqeMetadataVectorIndexService()
    documents = service.build_from_catalog(args.catalog_root, metadata_version=args.metadata_version)
    summary = service.index_documents(
        documents,
        apply=bool(args.apply_milvus),
        batch_size=args.batch_size,
    )
    payload = summary.to_dict()

    if args.apply_milvus and summary.errors:
        payload["warnings"] = list(payload.get("warnings") or []) + ["真实 Milvus 写入未完成：缺少显式注入的安全依赖"]

    if args.output_json:
        write_json(Path(args.output_json), payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
