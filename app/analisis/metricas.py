"""Las mismas fórmulas que publica Lichess, para que el número se parezca al suyo.

El front repite esto en `src/lib/analisis.ts`: si cambias una, cambia la otra.
"""
import math
from dataclasses import dataclass
from typing import Any

IMPRECISION = 5.0
ERROR = 10.0
ERROR_GRAVE = 15.0
CP_MATE = 10_000


def centipeones(evaluacion: dict[str, Any]) -> int:
    """Desde las blancas. Un mate cuenta como ventaja total."""
    if evaluacion.get("mate") is not None:
        mate = int(evaluacion["mate"])
        return CP_MATE if mate > 0 else -CP_MATE
    return int(evaluacion.get("cp") or 0)


def porcentaje_victoria(cp: int) -> float:
    cp = max(-1000, min(1000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def precision_jugada(antes: float, despues: float) -> float:
    caida = max(0.0, antes - despues)
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * caida) - 3.1669 + 1))


def clase(caida: float) -> str | None:
    if caida >= ERROR_GRAVE:
        return "error_grave"
    if caida >= ERROR:
        return "error"
    if caida >= IMPRECISION:
        return "imprecision"
    return None


@dataclass(frozen=True)
class Jugada:
    indice: int
    blancas: bool
    caida: float
    clase: str | None
    precision: float


def jugadas(eval_inicial: dict[str, Any], evals: list[dict[str, Any]], blancas_empiezan: bool = True) -> list[Jugada]:
    salida: list[Jugada] = []
    previo = porcentaje_victoria(centipeones(eval_inicial))
    for i, evaluacion in enumerate(evals):
        blancas = (i % 2 == 0) == blancas_empiezan
        actual = porcentaje_victoria(centipeones(evaluacion))
        antes, despues = (previo, actual) if blancas else (100 - previo, 100 - actual)
        caida = max(0.0, antes - despues)
        salida.append(Jugada(i, blancas, caida, clase(caida), precision_jugada(antes, despues)))
        previo = actual
    return salida


@dataclass(frozen=True)
class Totales:
    precision: float | None
    imprecisiones: int
    errores: int
    errores_graves: int


def totales(lista: list[Jugada], color: str) -> Totales:
    mias = [j for j in lista if j.blancas == (color == "white")]
    if not mias:
        return Totales(None, 0, 0, 0)
    return Totales(
        precision=round(sum(j.precision for j in mias) / len(mias), 1),
        imprecisiones=sum(1 for j in mias if j.clase == "imprecision"),
        errores=sum(1 for j in mias if j.clase == "error"),
        errores_graves=sum(1 for j in mias if j.clase == "error_grave"),
    )
