from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class CuentaLichess(Base, TimestampMixin):
    """`username` es el id estable de Lichess (minúsculas). El nombre visible puede cambiar."""

    __tablename__ = "cuentas_lichess"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    username_visible: Mapped[str] = mapped_column(String(64), nullable=False)
    vinculada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="cuenta_lichess")
