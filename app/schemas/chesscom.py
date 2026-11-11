from datetime import datetime

from pydantic import BaseModel, Field


class ChesscomConectarOut(BaseModel):
    url: str


class ChesscomVerificacionIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)


class ChesscomVerificacionOut(BaseModel):
    """`token` se devuelve tal cual al confirmar. Lleva el código firmado: no hace falta guardarlo."""

    username_visible: str
    codigo: str
    token: str
    expira_en: datetime


class ChesscomConfirmarIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)


class ChesscomEstadoOut(BaseModel):
    vinculada: bool
    username: str | None = None
    username_visible: str | None = None
