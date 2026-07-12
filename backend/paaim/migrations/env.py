import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Alembic config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Wire in PAAIM models so autogenerate picks up all tables + indexes
from paaim.models import Base  # noqa: E402
target_metadata = Base.metadata

# Pull DATABASE_URL_SYNC (sync driver) from env, falling back to alembic.ini value.
# Alembic does not support async drivers, so we use the sync URL here.
def get_url() -> str:
    return os.getenv("DATABASE_URL_SYNC") or config.get_main_option("sqlalchemy.url", "")


def run_migrations_offline() -> None:
    """Generate SQL script without a live DB connection."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
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
