from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SysQueryLog(Base):
    """查询日志表模型。

    风险说明：
    1. 当前 ORM 只作为字段约定说明和后续 Alembic 基础；
    2. 如果线上已有 `sys_query_log`，上线前必须核对字段类型和索引定义是否一致。
    """

    __tablename__ = "sys_query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    query_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[str] = mapped_column(Text, nullable=False)
    route_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metric_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
