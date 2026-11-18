"""Probabilidad de ganar y precisión con las fórmulas que publica Lichess; los
umbrales de error con los de Chess.com (puntos esperados perdidos: 0.05, 0.10, 0.20).

El front repite esto en `src/lib/analisis.ts`: si cambias una, cambia la otra.
"""
import math
from dataclasses import dataclass
from typing import Any

IMPRECISION = 5.0
ERROR = 10.0
ERROR_GRAVE = 20.0
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
    # Cuánto se movía la partida alrededor de esta jugada: las posiciones
    # agitadas pesan más en la precisión, como en Lichess.
    peso: float = 1.0


def _desviacion(valores: list[float]) -> float:
    media = sum(valores) / len(valores)
    return math.sqrt(sum((v - media) ** 2 for v in valores) / len(valores))


def _pesos(porcentajes: list[float], jugadas_totales: int) -> list[float]:
    ventana = max(2, min(8, jugadas_totales // 10))
    if len(porcentajes) <= ventana:
        ventanas = [porcentajes]
    else:
        ventanas = [porcentajes[i : i + ventana] for i in range(len(porcentajes) - ventana + 1)]
    ventanas = [porcentajes[:ventana]] * max(0, min(ventana, len(porcentajes)) - 2) + ventanas
    return [max(0.5, min(12.0, _desviacion(v))) for v in ventanas]


def jugadas(eval_inicial: dict[str, Any], evals: list[dict[str, Any]], blancas_empiezan: bool = True) -> list[Jugada]:
    porcentajes = [porcentaje_victoria(centipeones(e)) for e in [eval_inicial, *evals]]
    pesos = _pesos(porcentajes, len(evals))
    salida: list[Jugada] = []
    for i in range(len(evals)):
        blancas = (i % 2 == 0) == blancas_empiezan
        previo, actual = porcentajes[i], porcentajes[i + 1]
        antes, despues = (previo, actual) if blancas else (100 - previo, 100 - actual)
        caida = max(0.0, antes - despues)
        peso = pesos[i] if i < len(pesos) else pesos[-1]
        salida.append(Jugada(i, blancas, caida, clase(caida), precision_jugada(antes, despues), peso))
    return salida


def precision_partida(lista: list[Jugada]) -> float | None:
    """Media ponderada y media armónica, a partes iguales: un error grave pesa mucho."""
    if not lista:
        return None
    ponderada = sum(j.precision * j.peso for j in lista) / sum(j.peso for j in lista)
    armonica = len(lista) / sum(1 / max(1.0, j.precision) for j in lista)
    return round((ponderada + armonica) / 2, 1)


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
        precision=precision_partida(mias),
        imprecisiones=sum(1 for j in mias if j.clase == "imprecision"),
        errores=sum(1 for j in mias if j.clase == "error"),
        errores_graves=sum(1 for j in mias if j.clase == "error_grave"),
    )
