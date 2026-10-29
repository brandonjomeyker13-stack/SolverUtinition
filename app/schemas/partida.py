from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Plataforma, ResultadoPartida, Ritmo


class PartidaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plataforma: Plataforma
    plataforma_partida_id: str
    blanca_id: int
    negra_id: int
    ritmo: Ritmo
    rated_en_plataforma: bool
    resultado: ResultadoPartida
    elo_blanca_antes: int
    elo_negra_antes: int
    delta_blanca: int
    delta_negra: int
    terminada_en: datetime
    url: str | None


class SincronizacionOut(BaseModel):
    revisadas: int
    aplicadas: int
    omitidas: int
