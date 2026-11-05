from sqlalchemy.orm import Session

from app.models.enums import Ritmo
from app.models.rating import Rating
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.cuenta_lichess_repository import CuentaLichessRepository
from app.repositories.rating_repository import RatingRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.ranking import RankingFilaOut, RankingProgresoFilaOut


class RankingService:
    def __init__(self, db: Session):
        self.ratings = RatingRepository(db)
        self.usuarios = UsuarioRepository(db)
        self.cuentas = CuentaChesscomRepository(db)
        self.lichess = CuentaLichessRepository(db)

    def listar(self, ritmo: Ritmo, limit: int = 100) -> list[RankingFilaOut]:
        return [
            RankingFilaOut(**fila)
            for fila in self._filas(self.ratings.ranking(ritmo, limit), ritmo)
        ]

    def listar_progreso(self, ritmo: Ritmo, limit: int = 100) -> list[RankingProgresoFilaOut]:
        return [
            RankingProgresoFilaOut(**fila)
            for fila in self._filas(self.ratings.ranking_progreso(ritmo, limit), ritmo)
        ]

    def _filas(self, ratings: list[Rating], ritmo: Ritmo) -> list[dict]:
        cuentas = {c.usuario_id: c.username_visible for c in self.cuentas.listar_todas()}
        lichess = {c.usuario_id: c.username_visible for c in self.lichess.listar_todas()}
        salida: list[dict] = []
        for posicion, rating in enumerate(ratings, start=1):
            usuario = self.usuarios.get_by_id(rating.usuario_id)
            if usuario is None or not usuario.activo:
                continue
            salida.append(
                {
                    "posicion": posicion,
                    "usuario_id": usuario.id,
                    "nombre": usuario.nombre,
                    "chesscom_username": cuentas.get(usuario.id),
                    "lichess_username": lichess.get(usuario.id),
                    "ritmo": ritmo,
                    "elo": rating.elo,
                    "elo_inicio": rating.elo_inicio,
                    "subida": rating.subida,
                    "partidas_jugadas": rating.partidas_jugadas,
                }
            )
        return salida
