from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Plataforma

Color = Literal["white", "black"]
Resultado = Literal["gano", "perdio", "tablas"]


class JugadorOut(BaseModel):
    nombre: str
    elo: int | None


class PartidaGeneralOut(BaseModel):
    plataforma: Plataforma
    id: str
    url: str
    pgn: str
    blancas: JugadorOut
    negras: JugadorOut
    color: Color
    resultado: Resultado
    ritmo: str
    control: str
    terminada_en: datetime
    apertura: str | None
    analizada: bool = False
    precision: float | None = None


class Evaluacion(BaseModel):
    cp: int | None = None
    mate: int | None = None


class AnalisisIn(BaseModel):
    plataforma: Plataforma
    partida_id: str = Field(min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=500)
    color: Color
    ritmo: str = Field(max_length=20)
    resultado: Resultado
    apertura: str | None = Field(default=None, max_length=200)
    terminada_en: datetime
    pgn: str = Field(min_length=1, max_length=60_000)
    eval_inicial: Evaluacion
    evals: list[Evaluacion] = Field(max_length=1200)
    mejores: list[str | None] = Field(max_length=1200)
    segundas: list[Evaluacion | None] | None = Field(default=None, max_length=1200)


class AnalisisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plataforma: Plataforma
    partida_id: str
    color: Color
    eval_inicial: dict[str, Any]
    evals: list[dict[str, Any]]
    mejores: list[str | None]
    segundas: list[dict[str, Any] | None] | None = None
    precision: float | None
    imprecisiones: int
    errores: int
    errores_graves: int
    fuente: str


class PuzzleOut(BaseModel):
    fen: str
    solucion: str
    jugada: str
    caida: float
    plataforma: Plataforma
    partida_id: str
    url: str | None


class ResumenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    semana: date
    titulo: str
    puntos: list[str]
    datos: dict[str, Any]
    created_at: datetime


class SuscripcionPushIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=4, max_length=100)


class SuscripcionPushBorrar(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)


class ClavePushOut(BaseModel):
    clave: str | None
