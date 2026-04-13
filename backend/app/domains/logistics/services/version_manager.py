from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class LogisticsConfigVersionSnapshot:
    """配置版本快照。

    用途：
    1. 记录当前生效配置版本；
    2. 记录参与版本计算的文件数量；
    3. 给排查“为什么本次命中与上次不一样”提供上下文。
    """

    version: str
    file_count: int
    files: list[str]


class LogisticsConfigVersionManager:
    """物流查询配置版本管理器（V6）。

    说明：
    - 当前阶段不做数据库落库，只做运行期版本快照管理；
    - 版本号仍然基于文件修改时间快照生成；
    - 额外补充“参与版本计算的文件列表”，便于解释和调试。
    """

    def build_snapshot(self, version: str, files: Iterable[Path]) -> LogisticsConfigVersionSnapshot:
        file_list = sorted(str(p.resolve()) for p in files)
        return LogisticsConfigVersionSnapshot(
            version=version,
            file_count=len(file_list),
            files=file_list,
        )
