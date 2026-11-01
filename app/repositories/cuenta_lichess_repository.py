from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cuenta_lichess import CuentaLichess


class CuentaLichessRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_usuario_id(self, usuario_id: int) -> CuentaLichess | None:
        stmt = select(CuentaLichess).where(CuentaLichess.usuario_id == usuario_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_username(self, username: str) -> CuentaLichess | None:
        stmt = select(CuentaLichess).where(CuentaLichess.username == username.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def listar_todas(self) -> list[CuentaLichess]:
        return list(self.db.execute(select(CuentaLichess)).scalars().all())

    def create(self, cuenta: CuentaLichess) -> CuentaLichess:
        self.db.add(cuenta)
        self.db.flush()
        self.db.refresh(cuenta)
        return cuenta

    def delete(self, cuenta: CuentaLichess) -> None:
        self.db.delete(cuenta)
        self.db.flush()
