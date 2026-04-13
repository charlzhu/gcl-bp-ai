from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

engine = create_engine(settings.mysql_dsn, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

source_engine = create_engine(settings.source_mysql_dsn, pool_pre_ping=True, pool_recycle=3600)
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
