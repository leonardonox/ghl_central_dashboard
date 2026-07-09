from collections.abc import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.core.config import get_settings

settings = get_settings()


def _database_url() -> str:
    url = settings.database_url
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)

    if settings.environment.lower() in {'prod', 'production'} and url.startswith('sqlite'):
        raise RuntimeError('Em producao, use PostgreSQL persistente. SQLite pode perder dados no Render.')

    return url


engine = create_engine(_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    if 'daily_snapshots' not in inspector.get_table_names():
        return

    existing_columns = {column['name'] for column in inspector.get_columns('daily_snapshots')}
    additions = {
        'whatsapp_contacts': 'INTEGER DEFAULT 0 NOT NULL',
        'inbox_conversations': 'INTEGER DEFAULT 0 NOT NULL',
        'lead_channels': 'JSON',
        'metric_version': 'INTEGER DEFAULT 3 NOT NULL',
    }
    missing = [(name, ddl) for name, ddl in additions.items() if name not in existing_columns]
    if not missing:
        return

    with engine.begin() as connection:
        for name, ddl in missing:
            connection.execute(text(f'ALTER TABLE daily_snapshots ADD COLUMN {name} {ddl}'))
