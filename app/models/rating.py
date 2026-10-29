from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import Ritmo


class Rating(Base, TimestampMixin):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("usuario_id", "ritmo", name="uq_rating_usuario_ritmo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ritmo: Mapped[Ritmo] = mapped_column(
        Enum(Ritmo, name="ritmo_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    elo: Mapped[int] = mapped_column(Integer, nullable=False)
    partidas_jugadas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="ratings")
