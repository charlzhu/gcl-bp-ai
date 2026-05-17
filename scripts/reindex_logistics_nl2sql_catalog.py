#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (  # noqa: E402
    LogisticsCatalogRecallDocumentBuilder,
    LogisticsCatalogRecallService,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="重建物流 NL2SQL M2 Semantic Catalog Milvus 索引")
    parser.add_argument("--dry-run", action="store_true", help="只加载 catalog 并打印待索引文档数量，不访问 embedding/Milvus")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loader = LogisticsSemanticCatalogLoader()
    catalog = loader.load()
    builder = LogisticsCatalogRecallDocumentBuilder()
    documents = builder.build(catalog)

    if args.dry_run:
        doc_type_counts: dict[str, int] = {}
        for document in documents:
            doc_type_counts[document.doc_type] = doc_type_counts.get(document.doc_type, 0) + 1
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "catalog_version": catalog.catalog_version,
                    "documents": len(documents),
                    "doc_type_counts": doc_type_counts,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    service = LogisticsCatalogRecallService(catalog_loader=loader, document_builder=builder)
    result = service.index_catalog(catalog=catalog)
    print(json.dumps(result.model_dump(exclude={"hits"}), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
