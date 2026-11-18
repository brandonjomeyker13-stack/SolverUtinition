from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import Plataforma


class AnalisisPartida(Base, TimestampMixin):
    """Una partida general (no solo entre miembros) ya pasada por Stockfish.

    `evals[i]` es la evaluación después de la jugada i, desde las blancas:
    {"cp": 35} o {"mate": -3}. La de la posición inicial va en `eval_inicial`.
    `mejores[i]` es la mejor jugada (UCI) en la posición antes de la jugada i.
    `segundas[i]` es la evaluación de la segunda mejor jugada en esa misma
    posición (None si solo había una jugada legal o si no se calculó).
    """

    __tablename__ = "analisis_partidas"
    __table_args__ = (
        UniqueConstraint("usuario_id", "plataforma", "partida_id", name="uq_analisis_partida"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plataforma: Mapped[Plataforma] = mapped_column(
        Enum(Plataforma, name="plataforma_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    partida_id: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    color: Mapped[str] = mapped_column(String(5), nullable=False)
    ritmo: Mapped[str] = mapped_column(String(20), nullable=False)
    resultado: Mapped[str] = mapped_column(String(8), nullable=False)
    apertura: Mapped[str | None] = mapped_column(String(200), nullable=True)
    terminada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    pgn: Mapped[str] = mapped_column(Text, nullable=False)
    eval_inicial: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    mejores: Mapped[list[str | None]] = mapped_column(JSON, nullable=False)
    segundas: Mapped[list[dict[str, Any] | None] | None] = mapped_column(JSON, nullable=True)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    imprecisiones: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errores: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errores_graves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fuente: Mapped[str] = mapped_column(String(16), nullable=False)


class ResumenSemanal(Base, TimestampMixin):
    __tablename__ = "resumenes_semanales"
    __table_args__ = (UniqueConstraint("usuario_id", "semana", name="uq_resumen_semana"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semana: Mapped[date] = mapped_column(Date, nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    puntos: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    datos: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SuscripcionPush(Base, TimestampMixin):
    __tablename__ = "suscripciones_push"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
