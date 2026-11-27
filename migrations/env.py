from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.core.config import get_settings
from backend.app.models.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def get_url() -> str:
    """Return configured database URL or fallback to application settings."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = get_settings().database_url
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we don't
    even need a DBAPI to be available.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connect_args = {}
    if "sqlite" in configuration["sqlalchemy.url"]:
        connect_args["check_same_thread"] = False

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True if "sqlite" in get_url() else False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
