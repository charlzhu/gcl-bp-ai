from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LogisticsRagRepository:
    """物流 RAG 本地索引仓储。

    当前仓库没有已接通的 Milvus 运行环境，因此这里先提供：
    1. 本地 JSON 索引落盘；
    2. 查询时直接读回索引。

    这样可以保证最小版本先具备：
    - 文档导入
    - 向量入库
    - 检索验证
    """

    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path

    def exists(self) -> bool:
        """判断索引文件是否存在。"""
        return self.index_path.exists()

    def load(self) -> dict[str, Any]:
        """读取本地索引文件。"""
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> None:
        """保存本地索引文件。"""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
