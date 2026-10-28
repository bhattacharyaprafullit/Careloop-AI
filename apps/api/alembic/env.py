"""Alembic migration environment for CareLoop AI."""
import logging
from typing import Any

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db.models import Base

logger = logging.getLogger(__name__)

config = context.config
if not config.get_main_option("sqlalchemy.url") or config.get_main_option(
    "sqlalchemy.url"
) == "sqlite:///./careloop.db":
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or ""
    connect_args: dict[str, Any] = {}
    if "postgresql" in url:
        connect_args["prepare_threshold"] = 0
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
