from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Ritmo
from app.schemas.common import TimestampSchema


class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UsuarioOut(TimestampSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    activo: bool


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ritmo: Ritmo
    elo: int
    partidas_jugadas: int


class CuentaChesscomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    username_visible: str
    vinculada_en: datetime


class PerfilOut(UsuarioOut):
    chesscom: CuentaChesscomOut | None = None
    ratings: list[RatingOut] = []
