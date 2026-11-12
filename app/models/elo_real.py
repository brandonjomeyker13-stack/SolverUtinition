from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import Plataforma, Ritmo


class EloRealMes(Base, TimestampMixin):
    """Rating real de la cuenta en Lichess o Chess.com al empezar el mes y al cierre.

    `partidas` queda en null cuando la plataforma no lo da sin bajar todo el mes (Lichess).
    """

    __tablename__ = "elo_real_mensual"
    __table_args__ = (
        UniqueConstraint("usuario_id", "plataforma", "ritmo", "mes", name="uq_elo_real_mes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plataforma: Mapped[Plataforma] = mapped_column(
        Enum(Plataforma, name="plataforma_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    ritmo: Mapped[Ritmo] = mapped_column(
        Enum(Ritmo, name="ritmo_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    mes: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    elo_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    elo: Mapped[int] = mapped_column(Integer, nullable=False)
    partidas: Mapped[int | None] = mapped_column(Integer, nullable=True)
