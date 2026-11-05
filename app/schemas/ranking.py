from pydantic import BaseModel

from app.models.enums import Ritmo


class RankingFilaOut(BaseModel):
    posicion: int
    usuario_id: int
    nombre: str
    chesscom_username: str | None
    lichess_username: str | None = None
    ritmo: Ritmo
    elo: int
    partidas_jugadas: int


class RankingProgresoFilaOut(RankingFilaOut):
    """Ordenado por puntos subidos, no por elo actual. El front aún no lo muestra."""

    elo_inicio: int
    subida: int
