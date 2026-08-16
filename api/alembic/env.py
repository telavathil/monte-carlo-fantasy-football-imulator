from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.config import get_settings
from app.db import Base
from app.models import orm  # noqa: F401 — register models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# alembic.ini hardcodes a sqlalchemy.url, but the actual running app derives
# its database URL from app.config.Settings (DATA_DIR env var). If DATA_DIR
# is ever set to something other than alembic.ini's hardcoded default,
# alembic would silently migrate a *different* sqlite file than the one the
# app reads/writes — with no alembic_version tracking there, so a future
# migration would fail against a database that otherwise looks healthy.
# Override the ini value at runtime with the app's actual settings so both
# paths always agree.
config.set_main_option("sqlalchemy.url", get_settings().sqlite_url)


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
