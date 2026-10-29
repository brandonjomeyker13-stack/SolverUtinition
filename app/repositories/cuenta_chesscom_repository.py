from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cuenta_chesscom import CuentaChesscom


class CuentaChesscomRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_usuario_id(self, usuario_id: int) -> CuentaChesscom | None:
        stmt = select(CuentaChesscom).where(CuentaChesscom.usuario_id == usuario_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_username(self, username: str) -> CuentaChesscom | None:
        stmt = select(CuentaChesscom).where(CuentaChesscom.username == username.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def listar_todas(self) -> list[CuentaChesscom]:
        return list(self.db.execute(select(CuentaChesscom)).scalars().all())

    def create(self, cuenta: CuentaChesscom) -> CuentaChesscom:
        self.db.add(cuenta)
        self.db.flush()
        self.db.refresh(cuenta)
        return cuenta

    def delete(self, cuenta: CuentaChesscom) -> None:
        self.db.delete(cuenta)
        self.db.flush()
