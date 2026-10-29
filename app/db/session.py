from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}

if settings.usa_pooler_transaccional:
    # Transaction mode de Supabase (PgBouncer :6543): un pool encima de otro
    # deja conexiones colgadas. NullPool abre y cierra por request.
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.sqlalchemy_database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
