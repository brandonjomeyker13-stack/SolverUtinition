from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import Plataforma, ResultadoPartida, Ritmo


class Partida(Base, TimestampMixin):
    __tablename__ = "partidas"
    __table_args__ = (
        UniqueConstraint(
            "plataforma",
            "plataforma_partida_id",
            name="uq_partida_plataforma_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plataforma: Mapped[Plataforma] = mapped_column(
        Enum(Plataforma, name="plataforma_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    plataforma_partida_id: Mapped[str] = mapped_column(String(80), nullable=False)
    blanca_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    negra_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ritmo: Mapped[Ritmo] = mapped_column(
        Enum(Ritmo, name="ritmo_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    rated_en_plataforma: Mapped[bool] = mapped_column(Boolean, nullable=False)
    resultado: Mapped[ResultadoPartida] = mapped_column(
        Enum(
            ResultadoPartida,
            name="resultado_partida_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    elo_blanca_antes: Mapped[int] = mapped_column(Integer, nullable=False)
    elo_negra_antes: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_blanca: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_negra: Mapped[int] = mapped_column(Integer, nullable=False)
    terminada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pgn: Mapped[str | None] = mapped_column(Text, nullable=True)

    blanca: Mapped["Usuario"] = relationship(foreign_keys=[blanca_id])
    negra: Mapped["Usuario"] = relationship(foreign_keys=[negra_id])
