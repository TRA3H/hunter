import os
import sys
from logging.config import fileConfig

# Ensure the backend root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from sqlalchemy import create_engine, pool

from app.database import Base
from app.models import (  # noqa: F401 - ensure all models are imported
    Application,
    ApplicationLog,
    Education,
    Job,
    JobBoard,
    UserProfile,
    WorkExperience,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override with env var if available
database_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
if database_url and "+asyncpg" in database_url:
    database_url = database_url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
