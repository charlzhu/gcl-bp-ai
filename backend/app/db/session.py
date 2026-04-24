from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

engine = create_engine(settings.mysql_dsn, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 当前物流源库优先使用已确认可用的本机源库连接；
# 如果环境里显式配置了 SOURCE_MYSQL_*，仍按显式配置覆盖。
# connect_args 增加超时设置，防止远程源库查询时连接被提前断开
source_engine = create_engine(
    settings.resolved_source_mysql_dsn,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 30,
        "read_timeout": 300,
        "write_timeout": 300,
    },
)
SourceSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=source_engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_source_db() -> Iterator[Session]:
    db = SourceSessionLocal()
    try:
        yield db
    finally:
        db.close()
