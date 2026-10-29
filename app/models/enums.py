from enum import StrEnum


class Ritmo(StrEnum):
    BULLET = "bullet"
    BLITZ = "blitz"
    RAPID = "rapid"


class Plataforma(StrEnum):
    CHESSCOM = "chesscom"


class ResultadoPartida(StrEnum):
    BLANCA = "1-0"
    NEGRA = "0-1"
    TABLAS = "1/2-1/2"


RITMOS_QUE_CUENTAN = frozenset(Ritmo)
VARIANTES_QUE_CUENTAN = frozenset({"chess"})
