from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SysTaskErrorLog(Base):
    """系统任务错误日志表模型。

    风险说明：
    1. `raw_payload` 在线上通常是 JSON 字段，这里先用 `Text` 描述契约，避免和实际方言强绑定；
    2. 如果数据库已经存在 JSON 类型列，迁移时以线上真实结构为准。
    """

    __tablename__ = "sys_task_error_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    error_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    source_table_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_pk: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
