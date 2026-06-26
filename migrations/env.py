import os
from logging.config import fileConfig
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import engine_from_config, pool
from alembic import context

# Importa todos os models para o Alembic detectar
from app.models.base import Base
from app.models.user import User, UserSession
from app.models.api_connection import ApiConnection
from app.models.export import Export
from app.models.audit_log import AuditLog

config = context.config

# Sobrescreve a URL do alembic.ini com a variavel de ambiente
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
