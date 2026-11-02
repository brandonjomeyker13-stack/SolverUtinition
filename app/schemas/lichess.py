from pydantic import BaseModel, Field


class LichessConectarOut(BaseModel):
    url: str


class LichessVincularIn(BaseModel):
    username: str = Field(min_length=2, max_length=80)
