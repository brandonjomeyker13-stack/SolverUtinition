from pydantic import BaseModel


class ChesscomConectarOut(BaseModel):
    url: str


class ChesscomEstadoOut(BaseModel):
    vinculada: bool
    username: str | None = None
    username_visible: str | None = None
