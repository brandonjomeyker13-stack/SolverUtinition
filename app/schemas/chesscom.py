from pydantic import BaseModel, Field


class ChesscomConectarOut(BaseModel):
    url: str


class ChesscomVincularIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)


class ChesscomEstadoOut(BaseModel):
    vinculada: bool
    username: str | None = None
    username_visible: str | None = None
