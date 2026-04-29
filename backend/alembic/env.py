from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 把项目根目录放入 sys.path，保证 alembic 在任意工作目录都能导入 backend 包。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings  # noqa: E402
from backend.app.db.base import Base  # noqa: E402
import backend.app.models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_database_url() -> str:
    """解析 Alembic 运行时数据库连接串。

    优先级说明：
    1. 环境变量 `ALEMBIC_DATABASE_URL`；
    2. `alembic.ini` 里的 `sqlalchemy.url`；
    3. 应用正式配置里的 `settings.mysql_dsn`。
    """

    env_url = os.getenv("ALEMBIC_DATABASE_URL")
    if env_url:
        return env_url

    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url:
        return ini_url

    return settings.mysql_dsn


config.set_main_option("sqlalchemy.url", _resolve_database_url())

# 统一复用当前项目 ORM 元数据，后续新表迁移直接基于这里扩展。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式执行迁移。

    适用于只生成 SQL 脚本、不直接连接数据库的场景。
    """

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式执行迁移。

    适用于直接连接数据库并执行 upgrade / downgrade 的场景。
    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
