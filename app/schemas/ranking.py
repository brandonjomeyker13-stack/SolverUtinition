from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Plataforma, Ritmo


class RankingFilaOut(BaseModel):
    posicion: int
    usuario_id: int
    nombre: str
    chesscom_username: str | None
    lichess_username: str | None = None
    ritmo: Ritmo
    elo: int
    partidas_jugadas: int


class RankingMensualFilaOut(BaseModel):
    posicion: int
    usuario_id: int
    nombre: str
    chesscom_username: str | None
    lichess_username: str | None
    elo_inicio: int
    elo: int
    subida: int
    partidas: int
    ganadas: int
    tablas: int
    perdidas: int


class RankingMensualOut(BaseModel):
    """Puntos ganados en el mes, no elo actual: subir de 500 a 600 vale más que de 2000 a 2010.

    `elo_inicio` es el elo al empezar el mes; `elo`, el del cierre (o el actual si el mes sigue).
    """

    mes: str
    ritmo: Ritmo
    plataforma: Plataforma | None
    desde: datetime
    hasta: datetime
    filas: list[RankingMensualFilaOut]
