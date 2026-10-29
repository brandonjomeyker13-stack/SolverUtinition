from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import Plataforma
from app.models.partida import Partida


class PartidaRepository:
    def __init__(self, db: Session):
        self.db = db

    def existe(self, plataforma: Plataforma, plataforma_partida_id: str) -> bool:
        stmt = select(func.count()).select_from(Partida).where(
            Partida.plataforma == plataforma,
            Partida.plataforma_partida_id == plataforma_partida_id,
        )
        return self.db.execute(stmt).scalar_one() > 0

    def ids_existentes(self, plataforma: Plataforma, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        stmt = select(Partida.plataforma_partida_id).where(
            Partida.plataforma == plataforma,
            Partida.plataforma_partida_id.in_(ids),
        )
        return set(self.db.execute(stmt).scalars().all())

    def listar_de_usuario(self, usuario_id: int, offset: int = 0, limit: int = 50) -> list[Partida]:
        stmt = (
            select(Partida)
            .where((Partida.blanca_id == usuario_id) | (Partida.negra_id == usuario_id))
            .order_by(Partida.terminada_en.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, partida: Partida) -> Partida:
        self.db.add(partida)
        self.db.flush()
        self.db.refresh(partida)
        return partida
