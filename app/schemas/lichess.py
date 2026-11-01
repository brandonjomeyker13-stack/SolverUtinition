from pydantic import BaseModel


class LichessConectarOut(BaseModel):
    url: str
