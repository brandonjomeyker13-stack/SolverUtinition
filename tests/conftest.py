from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.enums import Ritmo
from app.models.rating import Rating
from app.models.usuario import Usuario


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _activar_llaves_foraneas(conexion, _registro):
        conexion.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sesion = sessionmaker(bind=engine)()
    try:
        yield sesion
    finally:
        sesion.close()


def _usuario(db: Session, nombre: str, email: str) -> Usuario:
    usuario = Usuario(
        nombre=nombre,
        email=email,
        password_hash=hash_password("clave-de-prueba-123"),
    )
    db.add(usuario)
    db.flush()
    for ritmo in Ritmo:
        db.add(
            Rating(
                usuario_id=usuario.id,
                ritmo=ritmo,
                elo=settings.ELO_INICIAL,
                partidas_jugadas=0,
            )
        )
    db.flush()
    return usuario


@pytest.fixture
def usuario_a(db: Session) -> Usuario:
    return _usuario(db, "Ana", "ana@prueba.com")


@pytest.fixture
def usuario_b(db: Session) -> Usuario:
    return _usuario(db, "Beto", "beto@prueba.com")


@pytest.fixture
def cuenta_a(db: Session, usuario_a: Usuario) -> CuentaChesscom:
    cuenta = CuentaChesscom(
        usuario_id=usuario_a.id,
        username="ana",
        username_visible="Ana",
        vinculada_en=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    db.add(cuenta)
    db.commit()
    db.refresh(cuenta)
    return cuenta


@pytest.fixture
def cuenta_b(db: Session, usuario_b: Usuario) -> CuentaChesscom:
    cuenta = CuentaChesscom(
        usuario_id=usuario_b.id,
        username="beto",
        username_visible="Beto",
        vinculada_en=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    db.add(cuenta)
    db.commit()
    db.refresh(cuenta)
    return cuenta
