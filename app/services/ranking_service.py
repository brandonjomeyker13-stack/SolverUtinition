from sqlalchemy.orm import Session

from app.models.enums import Ritmo
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.rating_repository import RatingRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.ranking import RankingFilaOut


class RankingService:
    def __init__(self, db: Session):
        self.ratings = RatingRepository(db)
        self.usuarios = UsuarioRepository(db)
        self.cuentas = CuentaChesscomRepository(db)

    def listar(self, ritmo: Ritmo, limit: int = 100) -> list[RankingFilaOut]:
        filas = self.ratings.ranking(ritmo, limit)
        cuentas = {c.usuario_id: c.username_visible for c in self.cuentas.listar_todas()}
        salida: list[RankingFilaOut] = []
        for posicion, rating in enumerate(filas, start=1):
            usuario = self.usuarios.get_by_id(rating.usuario_id)
            if usuario is None or not usuario.activo:
                continue
            salida.append(
                RankingFilaOut(
                    posicion=posicion,
                    usuario_id=usuario.id,
                    nombre=usuario.nombre,
                    chesscom_username=cuentas.get(usuario.id),
                    ritmo=ritmo,
                    elo=rating.elo,
                    partidas_jugadas=rating.partidas_jugadas,
                )
            )
        return salida
