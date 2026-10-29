from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Ritmo
from app.models.rating import Rating


class RatingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, usuario_id: int, ritmo: Ritmo) -> Rating | None:
        stmt = select(Rating).where(Rating.usuario_id == usuario_id, Rating.ritmo == ritmo)
        return self.db.execute(stmt).scalar_one_or_none()

    def listar_de_usuario(self, usuario_id: int) -> list[Rating]:
        stmt = select(Rating).where(Rating.usuario_id == usuario_id)
        return list(self.db.execute(stmt).scalars().all())

    def ranking(self, ritmo: Ritmo, limit: int = 100) -> list[Rating]:
        stmt = (
            select(Rating)
            .where(Rating.ritmo == ritmo)
            .order_by(Rating.elo.desc(), Rating.partidas_jugadas.desc(), Rating.usuario_id.asc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, rating: Rating) -> Rating:
        self.db.add(rating)
        self.db.flush()
        self.db.refresh(rating)
        return rating
